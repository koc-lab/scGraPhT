import math

import torch
from torch.nn.modules.module import Module
from torch.nn.parameter import Parameter


class GraphConvolution(Module):
    def __init__(self, in_features, out_features, bias=True):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.weight = Parameter(torch.FloatTensor(in_features, out_features))
        if bias:
            self.bias = Parameter(torch.FloatTensor(out_features))
        else:
            self.register_parameter("bias", None)
        self.reset_parameters()
    def reset_parameters(self):
        stdv = 2.0 / math.sqrt(self.weight.size(1))
        # self.weight.data.uniform_(-stdv, stdv)

        torch.nn.init.xavier_uniform_(self.weight, gain=torch.nn.init.calculate_gain("linear"))
        if self.bias is not None:
            self.bias.data.uniform_(-stdv, stdv)
    """
    def forward(self, x, adj):
        if x.shape[1] == 1:
            support = self.weight
        else:
            support = torch.mm(x, self.weight)
        output = torch.mm(adj, support)
        if self.bias is not None:
            return output + self.bias
        else:
            return output
    """

    def forward(self, x, adj):
   
        support = torch.mm(x, self.weight)
        output = torch.mm(adj, support)
        if self.bias is not None:
            return output + self.bias
        else:
            return output


    def __repr__(self):
        return self.__class__.__name__ + " (" + str(self.in_features) + " -> " + str(self.out_features) + ")"