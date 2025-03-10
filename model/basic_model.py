import torch
import torch.nn as nn
import torch.nn.functional as f
from .utils import GDN

class ResGDN(nn.Module):
    def __init__(self, in_channel, out_channel, kernel_size, stride, padding, inv=False):
        super(ResGDN, self).__init__()
        self.in_ch = int(in_channel)
        self.out_ch = int(out_channel)
        self.k = int(kernel_size)
        self.stride = int(stride)
        self.padding = int(padding)
        self.inv = bool(inv)
        self.conv1 = nn.Conv2d(self.in_ch, self.out_ch,
                               self.k, self.stride, self.padding)
        self.conv2 = nn.Conv2d(self.in_ch, self.out_ch,
                               self.k, self.stride, self.padding)
        self.ac1 = GDN(self.in_ch, self.inv)
        self.ac2 = GDN(self.in_ch, self.inv)

    def forward(self, x):
        x1 = self.ac1(self.conv1(x))
        x2 = self.conv2(x1)
        out = self.ac2(x + x2)
        return out


class ResBlock(nn.Module):
    def __init__(self, in_channel, out_channel, kernel_size, stride, padding):
        super(ResBlock, self).__init__()
        self.in_ch = int(in_channel)
        self.out_ch = int(out_channel)
        self.k = int(kernel_size)
        self.stride = int(stride)
        self.padding = int(padding)

        self.conv1 = nn.Conv2d(self.in_ch, self.out_ch,
                               self.k, self.stride, self.padding)
        self.conv2 = nn.Conv2d(self.in_ch, self.out_ch,
                               self.k, self.stride, self.padding)

    def forward(self, x):
        x1 = self.conv2(f.relu(self.conv1(x)))
        out = x+x1
        return out

# here use embedded gaussian

class Non_local_Block(nn.Module):
    def __init__(self, in_channel, out_channel):
        super(Non_local_Block, self).__init__()
        self.in_channel = in_channel
        self.out_channel = out_channel
        self.g = nn.Conv2d(self.in_channel, self.out_channel, 1, 1, 0)
        self.theta = nn.Conv2d(self.in_channel, self.out_channel, 1, 1, 0)
        self.phi = nn.Conv2d(self.in_channel, self.out_channel, 1, 1, 0)
        self.W = nn.Conv2d(self.out_channel, self.in_channel, 1, 1, 0)

        nn.init.constant_(self.W.weight, 0)
        nn.init.constant_(self.W.bias, 0)
        """ 
                        U
                        |    
            ----|--------|--------|
            |  theta     phi       g
            |    |        |        |
            |    -----X----(f1)    |
            |         |            |
            |         ------X-------()  
            |               |
            -------+--------
                   |
                   z
        """
    def forward(self, x):
        # x_size: (b c h w)
        batch_size = x.size(0)

        g_x = self.g(x).view(batch_size, self.out_channel, -1) # (b, g_out, h*w)
        g_x = g_x.permute(0, 2, 1) #(b, h*w, g_out)
        theta_x = self.theta(x).view(batch_size, self.out_channel, -1) # (b, theta_out, h*w)
        theta_x = theta_x.permute(0, 2, 1) # (b, h*w, theta_out)
        phi_x = self.phi(x).view(batch_size, self.out_channel, -1) # (b, phi_out, h*w)
        f1 = torch.matmul(theta_x, phi_x)
        f_div_C = f.softmax(f1, dim=-1)
        y = torch.matmul(f_div_C, g_x) # (batch_size, h*w, self.out_channel)
        y = y.permute(0, 2, 1).contiguous()
        y = y.view(batch_size, self.out_channel, *x.size()[2:])
        W_y = self.W(y)
        z = W_y+x
        return z


def conv1x1(in_ch: int, out_ch: int, stride: int = 1) -> nn.Module:
    """1x1 convolution."""
    return nn.Conv2d(in_ch, out_ch, kernel_size=1, stride=stride)


class ResidualBottleneck(nn.Module):
    def __init__(self, N=128, act=nn.ReLU) -> None:
        super().__init__()
        self.branch = nn.Sequential(
            conv1x1(N, N // 2),
            act(),
            nn.Conv2d(N // 2, N // 2, kernel_size=3, stride=1, padding=1),
            act(),
            conv1x1(N // 2, N)
        )

    def forward(self, x):
        out = x + self.branch(x)
        return out
