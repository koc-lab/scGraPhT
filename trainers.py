import copy
import time
from typing import Optional, Union
import numpy as np

import torch
from configs import Type4Input, TypeInput
from graph_models import Type3, Type12, Type4
from torch.nn import functional as F
from torch.optim import Optimizer
from tqdm.auto import tqdm

from utils_funcs import compute_metrics
import json


# Assuming the JSON file "vocab.json" is in the same directory as your Python script
file_path = "/auto/k2/aykut3/scgpt/scGPT/scgpt_gcn/save/dev_ms-Apr27-14-44/vocab.json"
pad_token="<pad>"
# Load the JSON file
with open(file_path, "r") as file:
    vocab = json.load(file)



# Set the device
device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

#TO DO: Early stopping will be added to training code
class TypeTrainer:
    def __init__(self, model: Union[Type12, Type3], optimizer: Optimizer, t_input: TypeInput):
        self.model = model
        self.optimizer = optimizer
        self.input = t_input
   
    # Commented lines are used for early stopping
    def pipeline(self, max_epochs: int, patience: int):
        
        t = tqdm(range(max_epochs))

        epoch_times, epoch_ct= [], 0
         

        for epoch in t:
            
            start_time = time.time()
            self.model.train()
            e_loss = 0
            e_loss = self.train_epoch()
            start_time=time.time()
            metrics, y_test_preds, y_test_true = self.evaluate()
            end_time=time.time()
            train_acc,test_acc,test_f1, valid_acc = metrics["train"]["acc"], metrics["test"]["acc"], metrics["test"]["macro"], metrics["valid"]["acc"] 
            t.set_description(f"Loss: {e_loss:.4f}, Test Acc: {100*test_acc:.3f},Train Acc: {100*train_acc:.3f},Test Macro F1: {100*test_f1:.3f}, Valid Acc: {100*valid_acc:.3f}")

            
            end_time= time.time()
            epoch_times.append(end_time - start_time)
            epoch_ct+=1
            
    
        self.avg_epoch_time = sum(epoch_times) / epoch_ct
        self.metrics= metrics
        self.y_test_preds= y_test_preds # these are numpy
        self.y_test_true= y_test_true   # these are numpy
        
        
  
    def train_epoch(self):
        self.optimizer.zero_grad()
        out = self.model(self.input.x, self.input.A_s)    
        loss = F.nll_loss(out[0:len(self.input.train_ids)], self.input.y[self.input.train_ids])
        loss.backward()
        e_loss = loss.item()
        self.optimizer.step()
        return e_loss

    def evaluate(self):
        metrics = {}
        
        with torch.no_grad():
            self.model.eval()
            
            out = self.model(self.input.x, self.input.A_s)
            metrics["train"] =compute_metrics(out[0:len(self.input.train_ids)], self.input.y[self.input.train_ids])
            metrics["test"] = compute_metrics(out[self.input.test_ids], self.input.y[self.input.test_ids])
            metrics["valid"]=compute_metrics(out[len(self.input.train_ids): len(self.input.train_ids)+ len(self.input.valid_ids)], self.input.y[self.input.valid_ids])

            ### These are test predictions
            y_test_preds= out[self.input.test_ids].max(1)[1]
            y_test_true = self.input.y[self.input.test_ids]
        
        return metrics, y_test_preds.cpu().numpy(), y_test_true.cpu().numpy()
    








###########################################################################

# On the way of building
class Type4Trainer:
    def __init__(self, model: Type4, optimizer: Optimizer, t_input: Type4Input, update_cls: bool = True):
        self.model = model
        self.optimizer = optimizer
        self.input = t_input
        self.cls_update=update_cls
        

    def pipeline(self, max_epochs: int, patience: int):
   
        t = tqdm(range(max_epochs))
       
        #es = EarlyStopping(patience=patience, verbose=True)
        

        epoch_times, epoch_ct, best_w_f1 = [], 0, 0

        for epoch in t:
            start_time = time.time()
            metrics = {}
            self.model.train()
            
            #start_time = time.time()
            e_loss= self.train_epoch()  
            #end_time = time.time()
            #print(f"********* {end_time-start_time} *************")



            
            metrics["test"] = self.evaluate(data_portion=2)
            metrics["valid"] = self.evaluate(data_portion=1)
            metrics["train"] = self.evaluate(data_portion=0)
            train_acc,test_acc,test_f1, valid_acc = metrics["train"]["acc"], metrics["test"]["acc"], metrics["test"]["macro"], metrics["valid"]["acc"] 
            t.set_description(f"Loss: {e_loss:.4f}, Test Acc: {100*test_acc:.3f},Train Acc: {100*train_acc:.3f},Test Macro F1: {100*test_f1:.3f}, Valid Acc: {100*valid_acc:.3f}")
            #best_valid_acc, best_valid_model = es(valid_acc, self.model, epoch)
            
            
            end_time = time.time()
            epoch_times.append(end_time - start_time)
            epoch_ct += 1  ## this is created as if they will a earlystopping!

            #if es.early_stop:
            #   break
        
        self.avg_epoch_time = sum(epoch_times) / epoch_ct
        self.metrics= metrics
      
        
            
    
    def train_epoch(self):

       
        id=0
    
        for batch_data in tqdm(self.input.loaders[0],leave=False):
           
            self.optimizer.zero_grad()
            input_gene_ids = batch_data["gene_ids"].to(device)          
            input_values = batch_data["values"].to(device)
            celltype_labels = batch_data["celltype_labels"].to(device)
            src_key_padding_mask = input_gene_ids.eq(vocab[pad_token])     
            idx=np.arange(id,id+len(input_gene_ids))
            id=id+len(input_gene_ids)
            out= self.model(self.input.x, self.input.A_s,input_gene_ids, input_values,src_key_padding_mask,idx)
            loss = F.nll_loss(out, celltype_labels)
            loss.backward()
            e_loss = loss.item()
            self.optimizer.step()
          

        return e_loss


    def evaluate(self, data_portion:int):
        with torch.no_grad():
            y_pred, y_true = [], []
            self.model.eval()
            
            # This if-else statement is crucial to set not to miss the indexes of each partition
            if data_portion==0:
                 id=0
            elif data_portion==1:
                id= len(self.input.train_ids) # self.input.train_ids
            elif data_portion==2:
                id=  len(self.input.train_ids)+ len(self.input.valid_ids)
            
            
            if self.cls_update:
                 temp_cls= self.input.x.clone()  
            time_counter=0
            for batch_data in tqdm(self.input.loaders[data_portion],leave=False):
                
               
                input_gene_ids = batch_data["gene_ids"].to(device)
                input_values = batch_data["values"].to(device)
                celltype_labels = batch_data["celltype_labels"].to(device)
                src_key_padding_mask = input_gene_ids.eq(vocab[pad_token])
                idx=np.arange(id,id+len(input_gene_ids))
                id=id+len(input_gene_ids)
                start_time=time.time()
                out= self.model(self.input.x, self.input.A_s,input_gene_ids, input_values,src_key_padding_mask,idx)
                end_time=time.time()
                time_counter=time_counter+(end_time-start_time)
                y_pred.append(out.cpu())
                y_true.append(celltype_labels.cpu())
                if self.cls_update:
                  temp_cls[idx]= self.model.encoder(input_gene_ids,input_values,src_key_padding_mask)["cell_emb"]
            
            if self.cls_update and data_portion==0: # Be carefull here
               
                self.input.x=temp_cls

            y_pred = torch.cat(y_pred, dim=0)
            y_true = torch.cat(y_true, dim=0)
            metrics = compute_metrics(y_pred, y_true)
            
            if data_portion==2:
                self.y_test_preds= y_pred.max(1)[1].numpy()
                self.y_test_true= y_true.numpy()
          
            return metrics

    
    
    #Currently, I dont use it
    def update_cls(self):
        
        with torch.no_grad():
            self.model.eval()
            
            id=0
            for batch_data in tqdm(self.input.loaders[0]):
                #print(id)

                input_gene_ids = batch_data["gene_ids"].to(device)
                input_values = batch_data["values"].to(device)
                src_key_padding_mask = input_gene_ids.eq(vocab[pad_token])
                out= self.model.encoder(input_gene_ids,input_values,src_key_padding_mask)["cell_emb"]
                idx=np.arange(id,id+len( input_gene_ids))
                id=id+len(input_gene_ids)
                self.input.x[idx] = out
                
            
            for batch_data in self.input.loaders[1]:

                #print(id)
                input_gene_ids = batch_data["gene_ids"].to(device)
                input_values = batch_data["values"].to(device)
                src_key_padding_mask = input_gene_ids.eq(vocab[pad_token])
                out= self.model.encoder(input_gene_ids,input_values,src_key_padding_mask)["cell_emb"]
                idx=np.arange(id,id+len(input_gene_ids))
                id=id+len(input_gene_ids)
                self.input.x[idx] = out
                


            for batch_data in self.input.loaders[2]:
                input_gene_ids = batch_data["gene_ids"].to(device)
                input_values = batch_data["values"].to(device)
                test_indices= batch_data["test_indices"] # we also can use it
                src_key_padding_mask = input_gene_ids.eq(vocab[pad_token])
                out= self.model.encoder(input_gene_ids,input_values,src_key_padding_mask)["cell_emb"]
                idx=np.arange(id,id+len(input_gene_ids))
                id=id+len(input_gene_ids)
                self.input.x[idx]=out


# I don't use this but you can try

class EarlyStopping:
    def __init__(self, patience: int, verbose: bool = False):
        self.patience = patience
        self.verbose = verbose

        self.counter: int = 0
        self.best_test_acc: float = 0.0
        self.best_model: Optional[torch.nn.Module] = None
        self.early_stop = False

    def __call__(self, test_acc: float, model: torch.nn.Module, epoch: int):
        if test_acc > self.best_test_acc:
            self.counter = 0
            self.best_test_acc = test_acc
            self.best_model = copy.deepcopy(model)
        else:
            self.counter += 1

        if self.counter >= self.patience:
            self.early_stop = True
            if self.verbose:
                print(f"Early stopping at epoch {epoch}")

        return self.best_test_acc, self.best_model