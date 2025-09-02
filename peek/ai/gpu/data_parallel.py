import os

os.environ["CUDA_VISIBLE_DEVICES"]="0"
import torch.nn as nn
import torchvision
from torch.utils.data import Dataset, DataLoader

class ConvNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 10, 5)
        self.conv2 = nn.Conv2d(10, 20, 3)
        self.fc1 = nn.Linear(20*10*10, 500)
        self.fc2 = nn.Linear(500, 10)
    def forward(self, x):
        in_size = x.size(0)
        out = self.conv1(x)
        out = F.relu(out)
        out = F.max_pool2d(out, 2, 2)
        out = self.conv2(out)
        out = F.relu(out)
        out = out.view(in_size, -1)
        out = self.fc1(out)
        out = F.relu(out)
        out = self.fc2(out)
        out = F.log_softmax(out, dim=1)
        return out

import  torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms
torch.__version__

BATCH_SIZE = 512
EPOCHS = 20

def train(model, train_loader, optimizer, epoch):
    model.train()
    for batch_idx, (data, target) in enumerate(train_loader):
        data, target = data.to(device0), target.to(device0)
        optimizer.zero_grad()
        output = model(data)
        loss = F.nll_loss(output, target)
        loss.backward()
        optimizer.step()
        if (batch_idx + 1) % 30 == 0:
            print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                epoch, batch_idx * len(data), len(train_loader.dataset),
                100. * batch_idx / len(train_loader), loss.item()))

device0=torch.device("cuda:0")

if __name__ == '__main__':
    BATCH_SIZE = 512
    EPOCHS = 20
    train_data = torchvision.datasets.MNIST(root='./data', train=True, transform=transforms.ToTensor(), download=True)
    train_loader = DataLoader(train_data, batch_size=50, shuffle=True, num_workers=4)
    model = ConvNet().cuda()
    model = nn.DataParallel(model, device_ids=[0]).to(device0)
    optimizer = optim.Adam(model.parameters())
    for  epoch in range(1, EPOCHS + 1):
        train(model, train_loader, optimizer, epoch)
    torch.save(model, "./MNIST.pth")



