"""
STAGATE model implementation.

Graph attention autoencoder for spatial transcriptomics.
Based on PyTorch Geometric framework.

Reference:
Dong et al. (2022). Deciphering spatial domains from spatially resolved
transcriptomics with an adaptive graph attention auto-encoder. Nature Communications.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.backends.cudnn as cudnn

cudnn.deterministic = True
cudnn.benchmark = True


class STAGATE(torch.nn.Module):
    """
    STAGATE Graph Attention Autoencoder.

    Parameters
    ----------
    hidden_dims : list
        List of dimensions [input_dim, hidden_dim, embedding_dim]

    Attributes
    ----------
    conv1 : GATConv
        First encoder layer with attention
    conv2 : GATConv
        Second encoder layer (embedding)
    conv3 : GATConv
        First decoder layer
    conv4 : GATConv
        Second decoder layer (reconstruction)
    """

    def __init__(self, hidden_dims):
        super(STAGATE, self).__init__()

        [in_dim, num_hidden, out_dim] = hidden_dims

        # Encoder layers
        self.conv1 = GATConv(
            in_dim, num_hidden,
            heads=1,
            concat=False,
            dropout=0,
            add_self_loops=False,
            bias=False
        )

        self.conv2 = GATConv(
            num_hidden, out_dim,
            heads=1,
            concat=False,
            dropout=0,
            add_self_loops=False,
            bias=False
        )

        # Decoder layers
        self.conv3 = GATConv(
            out_dim, num_hidden,
            heads=1,
            concat=False,
            dropout=0,
            add_self_loops=False,
            bias=False
        )

        self.conv4 = GATConv(
            num_hidden, in_dim,
            heads=1,
            concat=False,
            dropout=0,
            add_self_loops=False,
            bias=False
        )

    def forward(self, features, edge_index):
        """
        Forward pass through the autoencoder.

        Parameters
        ----------
        features : torch.Tensor
            Node features [N, F]
        edge_index : torch.Tensor
            Edge indices [2, E]

        Returns
        -------
        h2 : torch.Tensor
            Embedding representation [N, embedding_dim]
        h4 : torch.Tensor
            Reconstructed features [N, F]
        """
        # Encoder
        h1 = F.elu(self.conv1(features, edge_index))
        h2 = self.conv2(h1, edge_index, attention=False)

        # Decoder with tied weights
        self.conv3.lin_src.data = self.conv2.lin_src.transpose(0, 1)
        self.conv3.lin_dst.data = self.conv2.lin_dst.transpose(0, 1)
        self.conv4.lin_src.data = self.conv1.lin_src.transpose(0, 1)
        self.conv4.lin_dst.data = self.conv1.lin_dst.transpose(0, 1)

        h3 = F.elu(
            self.conv3(
                h2,
                edge_index,
                attention=True,
                tied_attention=self.conv1.attentions
            )
        )
        h4 = self.conv4(h3, edge_index, attention=False)

        return h2, h4


class GATConv(nn.Module):
    """
    Graph Attention Convolution layer.

    Custom implementation of GAT convolution with flexible attention control.

    Parameters
    ----------
    in_channels : int
        Input feature dimension
    out_channels : int
        Output feature dimension
    heads : int, default=1
        Number of attention heads
    concat : bool, default=False
        Whether to concatenate heads
    dropout : float, default=0
        Dropout rate
    add_self_loops : bool, default=False
        Whether to add self-loops
    bias : bool, default=False
        Whether to use bias
    """

    def __init__(
        self,
        in_channels,
        out_channels,
        heads=1,
        concat=False,
        dropout=0,
        add_self_loops=False,
        bias=False,
    ):
        super(GATConv, self).__init__()

        self.in_channels = in_channels
        self.out_channels = out_channels
        self.heads = heads
        self.concat = concat
        self.dropout = dropout
        self.add_self_loops = add_self_loops

        # Learnable parameters
        self.lin_src = nn.Parameter(torch.Tensor(in_channels, heads * out_channels))
        self.lin_dst = nn.Parameter(torch.Tensor(in_channels, heads * out_channels))

        if bias:
            self.bias = nn.Parameter(torch.Tensor(heads * out_channels if concat else out_channels))
        else:
            self.register_parameter('bias', None)

        # Attention parameters
        self.att_src = nn.Parameter(torch.Tensor(1, heads, out_channels))
        self.att_dst = nn.Parameter(torch.Tensor(1, heads, out_channels))

        self._alpha = None
        self.attentions = None

        self.reset_parameters()

    def reset_parameters(self):
        """Initialize parameters."""
        nn.init.xavier_uniform_(self.lin_src)
        nn.init.xavier_uniform_(self.lin_dst)
        nn.init.xavier_uniform_(self.att_src)
        nn.init.xavier_uniform_(self.att_dst)
        if self.bias is not None:
            nn.init.zeros_(self.bias)

    def forward(
        self,
        x,
        edge_index,
        attention=True,
        tied_attention=None,
        return_attention_weights=None,
    ):
        """
        Forward pass.

        Parameters
        ----------
        x : torch.Tensor
            Node features
        edge_index : torch.Tensor
            Edge indices
        attention : bool, default=True
            Whether to use attention
        tied_attention : torch.Tensor, optional
            Use pre-computed attention weights
        return_attention_weights : bool, optional
            Return attention weights

        Returns
        -------
        out : torch.Tensor
            Output features
        """
        # Linear transformation
        x_src = torch.mm(x, self.lin_src).view(-1, self.heads, self.out_channels)
        x_dst = torch.mm(x, self.lin_dst).view(-1, self.heads, self.out_channels)

        # Compute attention
        if attention:
            if tied_attention is not None:
                alpha = tied_attention
            else:
                # Compute attention scores
                alpha_src = (x_src * self.att_src).sum(dim=-1, keepdim=True)
                alpha_dst = (x_dst * self.att_dst).sum(dim=-1, keepdim=True)

                # Propagate
                src, dst = edge_index
                alpha = alpha_src[src] + alpha_dst[dst]
                alpha = torch.sigmoid(alpha)  # Sigmoid activation as in paper
                self.attentions = alpha

            # Apply attention
            out = self.propagate(edge_index, x=x_src, alpha=alpha)
        else:
            # No attention - simple aggregation
            out = self.propagate(edge_index, x=x_src, alpha=None)

        # Concatenate or mean over heads
        if self.concat:
            out = out.view(-1, self.heads * self.out_channels)
        else:
            out = out.mean(dim=1)

        if self.bias is not None:
            out = out + self.bias

        return out

    def propagate(self, edge_index, x, alpha=None):
        """
        Message propagation.

        Parameters
        ----------
        edge_index : torch.Tensor
            Edge indices [2, E]
        x : torch.Tensor
            Node features [N, H, F]
        alpha : torch.Tensor, optional
            Attention weights [E, H, 1]

        Returns
        -------
        out : torch.Tensor
            Aggregated features [N, H, F]
        """
        src, dst = edge_index

        # Gather source features
        messages = x[src]  # [E, H, F]

        # Apply attention weights
        if alpha is not None:
            messages = messages * alpha

        # Aggregate
        out = torch.zeros_like(x)
        out.index_add_(0, dst, messages)

        return out

    def __repr__(self):
        return f"{self.__class__.__name__}({self.in_channels}, {self.out_channels})"
