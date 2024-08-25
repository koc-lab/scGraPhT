import pickle
import random
import os
from pathlib import Path

import numpy as np
import torch
from dataset_graph import Dataset
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from torch.utils.data import DataLoader, TensorDataset

import sys
sys.path.insert(0, "../")
from scgpt import prepare_dataloader

"""

GC: #gene x #cell
CC: #cell x #cell
CG: #cell x #gene
GG: #gene x # gene

"""


def set_seeds(seed_no: int = 42):
    random.seed(seed_no)
    np.random.seed(seed_no)
    torch.manual_seed(seed_no)
    torch.cuda.manual_seed_all(seed_no)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = True  #this was originall true.But  you should set it to False to guarantee super reprodcubility in your code!!!!!



def compute_metrics(output, labels):
    preds = output.max(1)[1].type_as(labels)
    y_true = labels.cpu().numpy()
    y_pred = preds.cpu().numpy()
    w_f1 = f1_score(y_true, y_pred, average="weighted")
    macro = f1_score(y_true, y_pred, average="macro")
    micro = f1_score(y_true, y_pred, average="micro")
    acc = accuracy_score(y_true, y_pred)
    prec= precision_score(y_true,y_pred,average="macro",zero_division=0)
    recall=recall_score(y_true,y_pred,average="macro",zero_division=0)
    return {"w_f1": w_f1, "macro": macro, "micro": micro, "acc": acc,"precision":prec,"recall":recall}


# Set the device
device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')


def get_loaders(dataset_name,batch_size):

    loader_list=[]

    train_data_dict= torch.load(f"/auto/k2/aykut3/scgpt/scGPT/scgpt_gcn/save_scgcn/scgpt_{dataset_name}_median/train_loader.pth") 
    valid_data_dict= torch.load(f"/auto/k2/aykut3/scgpt/scGPT/scgpt_gcn/save_scgcn/scgpt_{dataset_name}_median/valid_loader.pth")
    test_data_dict= torch.load(f"/auto/k2/aykut3/scgpt/scGPT/scgpt_gcn/save_scgcn/scgpt_{dataset_name}_median/test_loader.pth")
  
    train_loader= prepare_dataloader(train_data_dict, batch_size=batch_size)
    valid_loader =  prepare_dataloader(valid_data_dict,batch_size=batch_size)
    test_loader= prepare_dataloader(test_data_dict,batch_size=batch_size)
    loader_list.append(train_loader)
    loader_list.append(valid_loader)
    loader_list.append(test_loader)
   
    return loader_list


def get_encoder_outputs(dataset_name):
    emb_path = f"/auto/k2/aykut3/scgpt/scGPT/scgpt_gcn/save_scgcn/scgpt_{dataset_name}_median/model_embeddings_{dataset_name}.pt"
    cls_logits_path = f"/auto/k2/aykut3/scgpt/scGPT/scgpt_gcn/save_scgcn/scgpt_{dataset_name}_median/model_logits_{dataset_name}.pt"
    x = torch.load(emb_path)
    cls_logits = torch.load(cls_logits_path)
    return x.to(device), cls_logits.to(device)


def get_variables(model_type: str, path, dataset: Dataset):
    unit_gene = torch.eye(dataset.GG.shape[0]).to(device)
    unit_cell = torch.eye(dataset.CC.shape[0]).to(device)
    name = dataset.dataset_name
    if model_type == "type1":
        if path[0] == "GG":
            x = unit_gene
            cls_logit = None
            fan_in = dataset.GG.shape[1]
            update_cls = False
        elif path[0] == "CG":
            x = unit_gene
            cls_logit = None
            fan_in = dataset.CG.shape[1]
            update_cls = False
        elif path[0] == "GC":
            x = unit_cell
            cls_logit = None
            fan_in = dataset.GC.shape[1]
            update_cls = False
        elif path[0] == "CC":
            x = unit_cell
            cls_logit = None
            fan_in = dataset.CC.shape[1]
            update_cls = False
        else:
            raise ValueError("Path must be one of GG-CG,CG-CC, GC-CG, CC-CC")
            
    elif model_type == "type2":
        if path[0] in ["GG","CG"]:
            x = unit_gene
            cls_logit = None
            fan_in = dataset.GG.shape[1]
            update_cls = False
        elif path[0] in ["CC","GC"]:
            x = get_encoder_outputs(name)[0]
            cls_logit = None
            fan_in = 512
            update_cls = False  
        else:
           raise ValueError("Path must be one of GG-CG,CG-CC, GC-CG, CC-CC")
           
    elif model_type == "type3":
        if path[0] in ["GG","CG"]:
            x = unit_gene
            cls_logit = get_encoder_outputs(name)[1]
            fan_in = dataset.GG.shape[1]
            update_cls = False
        elif path[0] in ["CC","GC"]:
            x, cls_logit = get_encoder_outputs(name)
            fan_in = 512
            update_cls = False          
        else:
            raise ValueError("Path must be one of GG-CG,CG-CC, GC-CG, CC-CC")

            
    elif model_type =="type4":
         if path[0] in ["GG","CG"]:
            x= unit_gene
            cls_logit= get_encoder_outputs(name)[1]
            fan_in = dataset.GG.shape[1]
            update_cls = False
         elif path[0] in ["CC","GC"]:
            x, cls_logit = get_encoder_outputs(name)
            fan_in = 512
            update_cls = True
         else:
            raise ValueError("Path must be one of GG-CG,CG-CC, GC-CG, CC-CC")

    return x, cls_logit, fan_in, update_cls


from graph_construct import genegene, cellgene, cellcell

def get_A_s(dataset: Dataset, path):
    expr_mat = dataset.expression_matrix_binned
    n_bins = 51
    adj_list = []

    for layer in path:
        if layer == "GG":
            adj_list.append(genegene(expr_mat).to(device))
        elif layer == "GC":
            adj_list.append(cellgene(expr_mat, n_bins).T.to(device))
        elif layer == "CG":
            adj_list.append(cellgene(expr_mat, n_bins).to(device))
        elif layer == "CC":
            adj_list.append(cellcell(expr_mat, 0.0).to(device))
        else:
            raise ValueError(f"Invalid layer combination: {layer}")               

    return adj_list  


def results_dict():
    return {
        "type":[],
        "dataset":[],
        "path": [],
        "test_acc": [],
        "test_recall":[],
        "test_precision":[],
        "test_f1": [],
        "test_preds":[],
        "test_true":[],
        "avg_epoch_time": [],

    }




if __name__=="__main__":   
   x,logits= get_encoder_outputs("ms")
   print(x.size())
   print(logits.size())
   # Print the device of the tensor
   print("Device x:", x.device)
   print("Device logits:", logits.device)
   loaders=get_loaders("ms",32)


  