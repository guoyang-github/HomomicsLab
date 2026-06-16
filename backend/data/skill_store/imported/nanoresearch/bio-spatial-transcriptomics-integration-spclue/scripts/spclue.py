import torch
import numpy as np

from .network import CCGCN, CCGCNs
from tqdm import tqdm
from .loss import ContrastiveLoss, ClusterLoss, MSELoss
from .utils import sparse_mx_to_torch_sparse_tensor, adjust_learning_rate, fix_seed

from sklearn.metrics import adjusted_rand_score


class spCLUE:
    """
    spCLUE: Contrastive Learning Approach to Unified Spatial Transcriptomics Analysis

    This class implements a graph contrastive learning framework for spatial
    transcriptomics data that integrates spatial location and gene expression
    to identify spatial domains. Supports both single-slice and multi-slice analysis.

    Parameters
    ----------
    input_data : np.ndarray
        PCA-reduced gene expression data (n_spots × n_features)
    graph_dict : dict
        Dictionary containing 'spatial' and 'expr' adjacency matrices
    n_clusters : int
        Number of spatial domains to identify (default: 12)
    batch_list : np.ndarray, optional
        Batch labels for multi-slice integration (default: None)
    epochs : int
        Number of training epochs (default: 500)
    random_seed : int
        Random seed for reproducibility (default: 0)
    device : torch.device
        Device for computation (default: cuda:0 if available)
    learning_rate : float
        Learning rate for optimizer (default: 0.001)
    weight_decay : float
        Weight decay for regularization (default: 0.001)
    dim_input : int
        Input feature dimension (default: 200)
    dim_hidden : int
        Hidden layer dimension (default: 64)
    dim_embed : int
        Embedding dimension (default: 24)
    graph_corr : float
        Graph corruption probability for edge dropout (default: 0.4)
    dropout : float
        Dropout probability (default: 0.5)
    gamma : float
        Weight for reconstruction loss (default: 1)
    beta : float
        Weight for cluster contrastive loss (default: 1)
    kappa : float
        Weight for instance contrastive loss (default: 0.1)
    batch_train : bool
        Whether to use batch training for large datasets (default: False)
    """

    def __init__(
        self,
        input_data,
        graph_dict,
        n_clusters=12,
        batch_list=None,
        epochs=500,
        random_seed=0,
        device=torch.device("cuda:0"),
        learning_rate=0.001,
        weight_decay=0.001,
        dim_input=200,
        dim_hidden=64,
        dim_embed=24,
        graph_corr=0.4,
        dropout=0.5,
        gamma=1,
        beta=1,
        kappa=0.1,
        batch_train=False,
    ):
        self.device = device
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.epochs = epochs

        self.n_clusters = n_clusters

        self.random_seed = random_seed
        self.graph_corr = graph_corr
        self.gamma = gamma
        self.beta = beta
        self.kappa = kappa
        self.dims_list = [dim_input, dim_hidden, dim_embed]
        self.n_spot = input_data.shape[0]

        fix_seed(self.random_seed)
        self.input_data = torch.FloatTensor(input_data).to(self.device)
        self.g_spatial = sparse_mx_to_torch_sparse_tensor(graph_dict["spatial"]).to(
            self.device
        )
        self.g_expr = sparse_mx_to_torch_sparse_tensor(graph_dict["expr"]).to(
            self.device
        )

        if batch_list is None:
            self.model = CCGCN(
                self.dims_list, self.n_clusters, self.graph_corr, dropout
            ).to(self.device)
        else:
            self.n_batches = len(set(batch_list))
            self.epochs = 500
            self.batchList = torch.LongTensor(batch_list).to(self.device)
            self.batch_train = batch_train
            self.model = CCGCNs(
                self.dims_list, self.n_clusters, self.n_batches, self.graph_corr
            ).to(self.device)

    def loss_idx(self):
        """Get indices for batch training to prevent OOM."""
        tmp = np.arange(self.n_spot)
        if self.batch_train:
            np.random.shuffle(tmp)
            return tmp[:20000]
        return tmp

    def updateResult(self, batch_case=False):
        """Update model results after training."""
        with torch.no_grad():
            self.model.eval()
            if batch_case:
                _, _, feature_spa, feature_expr, features_fuse, _, *_ = self.model(
                    self.input_data, self.g_spatial, self.g_expr, self.batchList
                )
                features_fuse = features_fuse.detach().cpu().numpy()
                return features_fuse

            _, _, feature_spa, feature_expr, features_fuse, _, *_ = self.model(
                self.input_data, self.g_spatial, self.g_expr
            )
            predLabel = self.model.getCluster(features_fuse)
            features_fuse = features_fuse.detach().cpu().numpy()
            predLabel = predLabel.detach().cpu().numpy()
            return predLabel, features_fuse

    def train(self):
        """
        Train spCLUE model for single-slice data.

        Returns
        -------
        predLabel : np.ndarray
            Predicted cluster labels for each spot
        features_fuse : np.ndarray
            Fused embedding features from spatial and expression views
        """
        self.instance_crit = ContrastiveLoss()
        self.cluster_crit = ClusterLoss(self.n_clusters, self.device)
        self.rec_crit = MSELoss()

        self.optimizer = torch.optim.Adam(
            filter(lambda p: p.requires_grad, self.model.parameters()),
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )
        max_ari = 0.3 if self.n_spot <= 10000 else 1.1
        print("Training Start =========================>")
        for epoch in tqdm(range(self.epochs)):
            self.model.train()
            adjust_learning_rate(self.optimizer, epoch, self.learning_rate, self.epochs)
            self.optimizer.zero_grad()

            (
                output1,
                output2,
                output_spa,
                output_expr,
                output_fuse,
                predlabel1,
                predlabel2,
                x_rec,
            ) = self.model(self.input_data, self.g_spatial, self.g_expr)

            cur_contrastive_loss = (
                self.instance_crit(output1, output2)
                + self.instance_crit(output2, output1)
            ) / 2
            cur_cluster_loss = self.cluster_crit(predlabel1, predlabel2)
            cur_rec_expr_loss = self.rec_crit(x_rec, self.input_data)

            cur_batch_loss = (
                self.kappa * cur_contrastive_loss
                + self.beta * cur_cluster_loss
                + self.gamma * cur_rec_expr_loss
            )
            cur_batch_loss.backward()
            self.optimizer.step()
            if (epoch + 1) % 100 == 0:
                predLabel1_np = predlabel1.detach().cpu().numpy().argmax(axis=1)
                predLabel2_np = predlabel2.detach().cpu().numpy().argmax(axis=1)
                cur_ari = adjusted_rand_score(predLabel1_np, predLabel2_np)
                print(f"epoch {epoch + 1}: {cur_ari}")
                if cur_ari >= max_ari:
                    predLabel, features_fuse = self.updateResult()
                    return predLabel, features_fuse

        print("Training Finished =================<")
        with torch.no_grad():
            self.model.eval()
            _, _, feature_spa, feature_expr, features_fuse, _, *_ = self.model(
                self.input_data, self.g_spatial, self.g_expr
            )
            predLabel = self.model.getCluster(features_fuse)
            features_fuse = features_fuse.detach().cpu().numpy()
            predLabel = predLabel.detach().cpu().numpy()

        return predLabel, features_fuse

    def trainBatch(self):
        """
        Train spCLUE model for multi-slice data with batch correction.

        Returns
        -------
        str
            Status message
        features_fuse : np.ndarray
            Fused embedding features with batch correction
        """
        self.instance_crit = ContrastiveLoss()
        self.rec_crit = MSELoss()
        self.cluster_crit = ClusterLoss(self.n_clusters, self.device)
        self.optimizer = torch.optim.Adam(
            filter(lambda p: p.requires_grad, self.model.parameters()),
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )
        max_ari = 0.5
        print("Training Start =========================>")
        for epoch in tqdm(range(self.epochs)):
            self.model.train()
            adjust_learning_rate(self.optimizer, epoch, self.learning_rate, self.epochs)
            self.optimizer.zero_grad()

            (
                output1,
                output2,
                _,
                _,
                output_fuse,
                x_rec,
                predlabel1,
                predlabel2,
            ) = self.model(self.input_data, self.g_spatial, self.g_expr, self.batchList)

            cur_loss_id = self.loss_idx()
            cur_contrastive_loss = (
                self.instance_crit(output1[cur_loss_id], output2[cur_loss_id])
                + self.instance_crit(output2[cur_loss_id], output1[cur_loss_id])
            ) / 2
            cur_cluster_loss = self.cluster_crit(
                predlabel1[cur_loss_id], predlabel2[cur_loss_id]
            )
            cur_rec_expr_loss = self.rec_crit(x_rec, self.input_data)

            cur_batch_loss = (
                self.kappa * cur_contrastive_loss
                + self.gamma * cur_rec_expr_loss
                + self.beta * cur_cluster_loss
            )

            cur_batch_loss.backward()
            self.optimizer.step()

            if (epoch + 1) % 100 == 0:
                predLabel1_np = predlabel1.detach().cpu().numpy().argmax(axis=1)
                predLabel2_np = predlabel2.detach().cpu().numpy().argmax(axis=1)
                cur_ari = round(adjusted_rand_score(predLabel1_np, predLabel2_np), 2)
                print(f"epoch {epoch + 1}: {cur_ari}")

                if epoch + 1 == 100:
                    self.kappa, self.beta = 0.0, 1.0

                if cur_ari >= max_ari:
                    features_fuse = self.updateResult(batch_case=True)
                    return "success", features_fuse
        print("Training Finished =================<")

        with torch.no_grad():
            self.model.eval()
            _, _, _, _, features_fuse, _, *_ = self.model(
                self.input_data, self.g_spatial, self.g_expr, self.batchList
            )
            features_fuse = features_fuse.detach().cpu().numpy()

        return "success", features_fuse
