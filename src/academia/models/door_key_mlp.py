import torch.nn as nn
import torch


class DoorKeyMLP(nn.Module):

    def __init__(self):
        super(DoorKeyMLP, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(51, 160),
            nn.ReLU(),
            nn.Linear(160, 100),
            nn.ReLU(),
            nn.Linear(100, 60),
            nn.ReLU(),
            nn.Linear(60, 5),
        )

    def forward(self, x) -> torch.Tensor:
        return self.network(x)
