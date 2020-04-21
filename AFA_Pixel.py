import torch
import torch.nn as nn
import torch.nn.functional as F


class CAM(nn.Module):
    def __init__(self, channels):
        super(CAM, self).__init__()
        self.gap = nn.AdaptiveAvgPool2d(1)

        self.fc_A = nn.Linear(in_features=channels * 8, out_features=round(channels / 2))
        self.bn1 = nn.BatchNorm1d(round(channels / 2))
        self.fc_AA = nn.Linear(in_features=round(channels / 2), out_features=channels * 4)
        self.fc_AB = nn.Linear(in_features=round(channels / 2), out_features=channels * 4)

        self.fc_B = nn.Linear(in_features=channels * 8, out_features=round(channels / 2))
        self.bn2 = nn.BatchNorm1d(round(channels / 2))
        self.fc_BA = nn.Linear(in_features=round(channels / 2), out_features=channels * 4)
        self.fc_BB = nn.Linear(in_features=round(channels / 2), out_features=channels * 4)

        self.relu = nn.ReLU(inplace=True)

    def forward(self, x1, x2):
        original_x1, original_x2 = x1.data, x2.data
        d_A = self.gap(original_x1)
        d_B = self.gap(original_x2)
        d_concate = torch.cat((d_A, d_B), dim=1)
        d_concate = d_concate.view(d_concate.size(0), -1)

        g_A = self.relu(self.bn1(self.fc_A(d_concate)))
        w_AA = torch.unsqueeze(self.relu(self.fc_AA(g_A)), dim=1)
        w_AB = torch.unsqueeze(self.relu(self.fc_AB(g_A)), dim=1)
        w = torch.cat((w_AA, w_AB), dim=1)
        w = F.softmax(w, dim=1).permute(1, 0, 2)
        w_AA = w[0].view(w[0].size(0), w[0].size(1), 1, 1)
        w_AB = w[1].view(w[1].size(0), w[1].size(1), 1, 1)
        out1 = x1 + w_AA * original_x1 + w_AB * original_x2 - original_x1

        g_B = self.relu(self.bn2(self.fc_B(d_concate)))
        w_BA = torch.unsqueeze(self.relu(self.fc_BA(g_B)), dim=1)
        w_BB = torch.unsqueeze(self.relu(self.fc_BB(g_B)), dim=1)
        w = torch.cat((w_BA, w_BB), dim=1)
        w = F.softmax(w, dim=1).permute(1, 0, 2)
        w_BA = w[0].view(w[0].size(0), w[0].size(1), 1, 1)
        w_BB = w[1].view(w[1].size(0), w[1].size(1), 1, 1)
        out2 = x2 + w_BA * original_x1 + w_BB * original_x2 - original_x2
        return out1, out2


class SAM(nn.Module):
    def __init__(self):
        super(SAM, self).__init__()

        self.conv_A = nn.Conv2d(in_channels=2, out_channels=1, kernel_size=1, stride=1, padding=0)
        self.fc_AA = nn.Linear(in_features=361, out_features=361)
        self.fc_AB = nn.Linear(in_features=361, out_features=361)
        self.conv_B = nn.Conv2d(in_channels=2, out_channels=1, kernel_size=1, stride=1, padding=0)
        self.fc_BA = nn.Linear(in_features=361, out_features=361)
        self.fc_BB = nn.Linear(in_features=361, out_features=361)

        self.relu = nn.ReLU(inplace=True)
        self.bn1 = nn.BatchNorm2d(1)
        self.bn2 = nn.BatchNorm2d(1)

    def forward(self, x1, x2):
        b, c, height, width = x1.size()
        original_x1, original_x2 = x1.data, x2.data
        d_A = torch.mean(original_x1, dim=1, keepdim=True)
        d_B = torch.mean(original_x2, dim=1, keepdim=True)
        d_concat = torch.cat((d_A, d_B), dim=1)

        g_A = self.relu(self.bn1(self.conv_A(d_concat)))
        g_A_vector = g_A.view(b, -1)
        w_AA = torch.unsqueeze(self.relu(self.fc_AA(g_A_vector)), dim=1)
        w_AB = torch.unsqueeze(self.relu(self.fc_AB(g_A_vector)), dim=1)
        w = torch.cat((w_AA, w_AB), dim=1)
        w = F.softmax(w, dim=1).permute(1, 0, 2)
        w_AA = w[0].view(w[0].size(0), -1, height, width)
        w_AB = w[1].view(w[1].size(0), -1, height, width)
        out1 = x1 + w_AA * original_x1 + w_AB * original_x2 - original_x1

        g_B = self.relu(self.bn2(self.conv_B(d_concat)))
        g_B_vector = g_B.view(b, -1)
        w_BA = torch.unsqueeze(self.relu(self.fc_BA(g_B_vector)), dim=1)
        w_BB = torch.unsqueeze(self.relu(self.fc_BB(g_B_vector)), dim=1)
        w = torch.cat((w_BA, w_BB), dim=1)
        w = F.softmax(w, dim=1).permute(1, 0, 2)
        w_BA = w[0].view(w[0].size(0), -1, height, width)
        w_BB = w[1].view(w[1].size(0), -1, height, width)
        out2 = x2 + w_BA * original_x1 + w_BB * original_x2 - original_x2

        return out1, out2


class AFA_layer(nn.Module):

    def __init__(self, channels=512):
        super(AFA_layer, self).__init__()
        self.cam = CAM(channels)
        self.sam = SAM()

    def forward(self, x1, x2):
        x1, x2 = self.cam(x1, x2)
        x1, x2 = self.sam(x1, x2)
        return x1, x2

