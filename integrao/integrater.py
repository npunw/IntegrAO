from integrao.unsupervised_train import tsne_p_deep
from integrao.supervised_train import tsne_p_deep_classification

from integrao.main import dist2, integrao_fuse, _stable_normalized
from integrao.util import data_indexing

import snf
import pandas as pd
import numpy as np

class integrao_integrater(object):
    def __init__(
        self,
        datasets,
        dataset_name=None,
        neighbor_size=None,
        embedding_dims=50,
        fusing_iteration=20,
        normalization_factor=1.0,
        alighment_epochs=1000,
        beta=1.0,
        mu=0.5,
        mask=False,
    ):
        self.datasets = datasets
        self.dataset_name = dataset_name
        self.embedding_dims = embedding_dims
        self.fusing_iteration = fusing_iteration
        self.normalization_factor = normalization_factor
        self.alighment_epochs = alighment_epochs
        self.beta = beta
        self.mu = mu
        self.mask = False

        # data indexing
        (
            self.dicts_common,
            self.dicts_commonIndex,
            self.dict_sampleToIndexs,
            self.dicts_unique,
            self.original_order,
            self.dict_original_order,
        ) = data_indexing(self.datasets)

        # set neighbor size
        if neighbor_size==None:
            self.neighbor_size = int(datasets[0].shape[0] / 6)
        else:
            self.neighbor_size = neighbor_size
        print("Neighbor size:", self.neighbor_size)

    def network_diffusion(self):
        S_dfs = []
        for i in range(0, len(self.datasets)):
            view = self.datasets[i]
            dist_mat = dist2(view.values, view.values)
            S_mat = snf.compute.affinity_matrix(dist_mat, K=self.neighbor_size, mu=self.mu)
            
            S_df = pd.DataFrame(data=S_mat, index=self.original_order[i], columns=self.original_order[i])

            S_dfs.append(S_df)

        self.fused_networks = snf2(
            S_dfs.copy(),
            dicts_common=self.dicts_common,
            dicts_unique=self.dicts_unique,
            original_order=self.original_order,
            neighbor_size=self.neighbor_size,
            fusing_iteration=self.fusing_iteration,
            normalization_factor=self.normalization_factor,
        )
        return self.fused_networks

    
    def unsupervised_alignment(self):
        # turn pandas dataframe into np array
        datasets_val = [x.values for x in self.datasets]
        fused_networks_val = [x.values for x in self.fused_networks]

        S_final, self.models = tsne_p_deep(
            self.dicts_commonIndex,
            self.dict_sampleToIndexs,
            datasets_val,
            P=fused_networks_val,
            neighbor_size=self.neighbor_size,
            embedding_dims=self.embedding_dims,
            alighment_epochs=self.alighment_epochs,
        )

        self.final_embeds = pd.DataFrame(data=S_final, index=self.dict_sampleToIndexs.keys())
        self.final_embeds.sort_index(inplace=True)

        # calculate the final similarity graph
        dist_final = dist2(self.final_embeds.values, self.final_embeds.values)
        Wall_final = snf.compute.affinity_matrix(dist_final, K=self.neighbor_size, mu=self.mu)

        Wall_final = _stable_normalized(Wall_final)

        return self.final_embeds, Wall_final, self.models
        
    def classification_finetuning(self, clf_labels, model_path, finetune_epochs=1000):
        # turn pandas dataframe into np array
        datasets_val = [x.values for x in self.datasets]
        fused_networks_val = [x.values for x in self.fused_networks]

        # reorder of clf_labels to make it the same with self.dict_sampleToIndexs.keys()
        clf_labels = clf_labels.loc[self.dict_sampleToIndexs.keys()]

        S_final, self.models, preds = tsne_p_deep_classification(
            self.dicts_commonIndex,
            self.dict_sampleToIndexs,
            self.dict_original_order,
            datasets_val,
            clf_labels,
            P=fused_networks_val,
            model_path=model_path,
            neighbor_size=self.neighbor_size,
            embedding_dims=self.embedding_dims,
            alighment_epochs=finetune_epochs,
            num_classes=len(np.unique(clf_labels)),
        )

        self.final_embeds = pd.DataFrame(data=S_final, index=self.dict_sampleToIndexs.keys())
        self.final_embeds.sort_index(inplace=True)

        # calculate the final similarity graph
        dist_final = dist2(self.final_embeds.values, self.final_embeds.values)
        Wall_final = snf.compute.affinity_matrix(dist_final, K=self.neighbor_size, mu=self.mu)

        Wall_final = _stable_normalized(Wall_final)

        return self.final_embeds, Wall_final, self.models, preds

    