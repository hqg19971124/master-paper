import torch.nn as nn
import torchvision.models as m
import torch
import math
import numpy as np


class NDDR(nn.Module):

    def __init__(self, in_channels, out_channels):
        super(NDDR, self).__init__()
        self.in_channels = in_channels
        self.nddr_1 = nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=1, padding=0, bias=False)
        self.bn_1 = nn.BatchNorm2d(out_channels)
        self.nddr_2 = nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=1, padding=0, bias=False)
        self.bn_2 = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

        if isinstance(self.nddr_1, nn.Conv2d):
            temp = torch.Tensor(np.zeros(self.nddr_1.weight.shape))
            for i in range(self.nddr_1.out_channels):
                temp[i][i] = 0.9
                temp[i][i + self.nddr_1.out_channels] = 0.1
            self.nddr_1.weight = torch.nn.Parameter(temp)

        if isinstance(self.nddr_2, nn.Conv2d):
            temp = torch.Tensor(np.zeros(self.nddr_2.weight.shape))
            for i in range(self.nddr_2.out_channels):
                temp[i][i] = 0.1
                temp[i][i + self.nddr_2.out_channels] = 0.9
            self.nddr_2.weight = torch.nn.Parameter(temp)

        if isinstance(self.bn_1, nn.BatchNorm2d):
            self.bn_1.weight.data.fill_(1)
            self.bn_1.bias.data.zero_()
        if isinstance(self.bn_2, nn.BatchNorm2d):
            self.bn_2.weight.data.fill_(1)
            self.bn_2.bias.data.zero_()

    def forward(self, input1, input2):
        x = torch.cat((input1, input2), dim=1)
        x1 = self.nddr_1(x)
        x1 = self.bn_1(x1)
        o1 = self.relu(x1)
        x2 = self.nddr_2(x)
        x2 = self.bn_2(x2)
        o2 = self.relu(x2)

        return o1, o2


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, inplanes, planes, stride=1, A_downsample=None, B_downsample=None):
        super(Bottleneck, self).__init__()
        self.planes = planes

        self.A_conv1 = nn.Conv2d(inplanes, planes, kernel_size=1, bias=False)
        self.A_bn1 = nn.BatchNorm2d(planes)
        self.A_conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.A_bn2 = nn.BatchNorm2d(planes)
        self.A_conv3 = nn.Conv2d(planes, planes * 4, kernel_size=1, bias=False)
        self.A_bn3 = nn.BatchNorm2d(planes * 4)
        self.A_relu = nn.ReLU(inplace=True)

        self.B_conv1 = nn.Conv2d(inplanes, planes, kernel_size=1, bias=False)
        self.B_bn1 = nn.BatchNorm2d(planes)
        self.B_conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.B_bn2 = nn.BatchNorm2d(planes)
        self.B_conv3 = nn.Conv2d(planes, planes * 4, kernel_size=1, bias=False)
        self.B_bn3 = nn.BatchNorm2d(planes * 4)
        self.B_relu = nn.ReLU(inplace=True)


        self.A_downsample = A_downsample
        self.B_downsample = B_downsample
        self.stride = stride

    def forward(self, x):
        x1, x2 = x[0], x[1]
        residual_1 = x1
        residual_2 = x2

        out1 = self.A_conv1(x1)
        out1 = self.A_bn1(out1)
        out1 = self.A_relu(out1)

        out1 = self.A_conv2(out1)
        out1 = self.A_bn2(out1)
        out1 = self.A_relu(out1)

        out1 = self.A_conv3(out1)
        out1 = self.A_bn3(out1)

        out2 = self.B_conv1(x2)
        out2 = self.B_bn1(out2)
        out2 = self.B_relu(out2)

        out2 = self.B_conv2(out2)
        out2 = self.B_bn2(out2)
        out2 = self.B_relu(out2)

        out2 = self.B_conv3(out2)
        out2 = self.B_bn3(out2)

        if self.A_downsample is not None:
            residual_1 = self.A_downsample(x1)
        if self.B_downsample is not None:
            residual_2 = self.B_downsample(x2)
        out1 += residual_1
        out2 += residual_2
        out1 = self.A_relu(out1)
        out2 = self.B_relu(out2)

        return out1, out2


class ResNet(nn.Module):

    def __init__(self, block, layers, num_classes1=2, num_classes2=8):
        self.inplanes = 64
        super(ResNet, self).__init__()

        self.A_conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.A_bn1 = nn.BatchNorm2d(64)
        self.A_relu = nn.ReLU(inplace=True)
        self.A_maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.B_conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.B_bn1 = nn.BatchNorm2d(64)
        self.B_relu = nn.ReLU(inplace=True)
        self.B_maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)

        self.layer1 = self._make_layer(block, 64, layers[0])
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2)

        self.A_avgpool = nn.AvgPool2d(7, stride=1)
        self.A_fc = nn.Linear(512 * block.expansion, num_classes1)
        self.B_avgpool = nn.AvgPool2d(7, stride=1)
        self.B_fc = nn.Linear(512 * block.expansion, num_classes2)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()
            elif isinstance(m, nn.Linear):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm1d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

        self.NDDR_1 = NDDR(512, 256)
        self.NDDR_2 = NDDR(1024, 512)
        self.NDDR_3 = NDDR(2048, 1024)
        self.NDDR_4 = NDDR(4096, 2048)

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * block.expansion,
                          kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion),
            )
        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample, downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes))

        return nn.Sequential(*layers)

    def forward(self, x):
        x1 = self.A_conv1(x)
        x1 = self.A_bn1(x1)
        x1 = self.A_relu(x1)
        x1 = self.A_maxpool(x1)
        x2 = self.B_conv1(x)
        x2 = self.B_bn1(x2)
        x2 = self.B_relu(x2)
        x2 = self.B_maxpool(x2)
        x = (x1, x2)
        x1, x2 = self.layer1(x)
        x1, x2 = self.NDDR_1(x1, x2)
        x = (x1, x2)
        x1, x2 = self.layer2(x)
        x1, x2 = self.NDDR_2(x1, x2)
        x = (x1, x2)
        x1, x2 = self.layer3(x)
        x1, x2 = self.NDDR_3(x1, x2)
        x = (x1, x2)
        x1, x2 = self.layer4(x)
        x1, x2 = self.NDDR_4(x1, x2)

        x1 = self.A_avgpool(x1)
        x1 = x1.view(x1.size(0), -1)
        x1 = self.A_fc(x1)
        x2 = self.B_avgpool(x2)
        x2 = x2.view(x2.size(0), -1)
        x2 = self.B_fc(x2)

        return x1, x2

    def get_1x_lr_params(self):
        modules = [self.A_conv1, self.A_bn1, self.B_conv1, self.B_bn1, self.layer1, self.layer2, self.layer3, self.layer4, self.NDDR_1, self.NDDR_2, self.NDDR_3, self.NDDR_4]
        for i in range(len(modules)):
            for m in modules[i].named_modules():
                if isinstance(m[1], nn.Conv2d) or isinstance(m[1], nn.BatchNorm2d) or isinstance(m[1], nn.BatchNorm1d) or isinstance(m[1], nn.Linear):
                    for p in m[1].parameters():
                        if p.requires_grad:
                            yield p

    def get_10x_lr_params(self):
        modules = [self.A_fc, self.B_fc]
        for i in range(len(modules)):
            for m in modules[i].named_modules():
                if isinstance(m[1], nn.BatchNorm1d) or isinstance(m[1], nn.Linear):
                    for p in m[1].parameters():
                        if p.requires_grad:
                            yield p


def make_network():
    resnet101 = m.resnet101(pretrained=True)
    pretrained_dict = resnet101.state_dict()

    pre_dict_1 = {'A_' + k: v for k, v in pretrained_dict.items() if k[:5] != 'layer' and k[:2] != 'fc'}
    pre_dict_2 = {k[:9] + 'A_' + k[9:]: v for k, v in pretrained_dict.items() if k[:5] == 'layer' and k[9] != '.'}
    pre_dict_3 = {k[:10] + 'A_' + k[10:]: v for k, v in pretrained_dict.items() if k[:5] == 'layer' and k[9] == '.'}
    pre_dict_4 = {'B_' + k: v for k, v in pretrained_dict.items() if k[:5] != 'layer' and k[:2] != 'fc'}
    pre_dict_5 = {k[:9] + 'B_' + k[9:]: v for k, v in pretrained_dict.items() if k[:5] == 'layer' and k[9] != '.'}
    pre_dict_6 = {k[:10] + 'B_' + k[10:]: v for k, v in pretrained_dict.items() if k[:5] == 'layer' and k[9] == '.'}

    net = ResNet(Bottleneck, [3, 4, 23, 3])
    net_dict = net.state_dict()
    net_dict.update(pre_dict_1)
    net_dict.update(pre_dict_2)
    net_dict.update(pre_dict_3)
    net_dict.update(pre_dict_4)
    net_dict.update(pre_dict_5)
    net_dict.update(pre_dict_6)
    net.load_state_dict(net_dict)
    return net





