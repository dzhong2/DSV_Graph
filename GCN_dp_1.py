from utils import *
import numpy as np
import glob
from igraph import *
from pygcn import GCN
from torch import optim
import torch.nn.functional as F
import time
import pickle as pkl
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score


def get_all_ids(database):
    files = glob.glob("dataset/" + database + '/*.pkl')
    ids = []
    for file in files:
        id = int(file.split('-')[0].split('\\')[1])
        ids.append(id)
    return ids


def map_labels(labels, c_list):
    new_label = []
    for i in range(len(labels)):
        current_id = labels[i]
        new_id = int(np.where(np.unique(c_list) == current_id)[0])
        new_label.append(new_id)
    return np.array(new_label)


def accuracy(output, labels):
    preds = output.max(1)[1].type_as(labels)
    correct = preds.eq(labels).double()
    correct = correct.sum()
    return correct / len(labels)


def run_GCN(gender, ft, adj, labels, epochs, ego='', dataset="facebook", saving_path="gcn",
            DP=False, lbd=np.inf, Ptb=False, gamma=torch.inf):
    if len(labels.shape) > 1:
        if torch.is_tensor(labels):
            labels = labels.argmax(dim=1)
        else:
            labels = torch.Tensor(labels.argmax(axis=1))

    if "tagged" in dataset:
        nhid = 20
        dropout = 0.5
        lr = 0.005
        train, val = 0.6, 0.2
        patience = 20
    else:
        nhid = 32
        dropout = 0.5
        lr = 0.01
        train, val = 0.6, 0.2
        patience = 20

    if adj.is_sparse:
        adj = adj.to_dense()
    if adj.dtype == torch.int64:
        adj = adj.float()

    idx_random = np.arange(len(labels))
    np.random.shuffle(idx_random)
    idx_train = torch.LongTensor(idx_random[:int(len(labels) * train)])
    idx_val = torch.LongTensor(idx_random[int(len(labels) * train):int(len(labels) * (train + val))])
    idx_test = torch.LongTensor(idx_random[int(len(labels) * (train + val)):])
    ss = StandardScaler()
    ft = torch.FloatTensor(ss.fit_transform(ft))

    model = GCN(nfeat=ft.shape[1],
                nhid=nhid,
                nclass=labels.max().item() + 1,
                dropout=dropout,
                DP=DP,
                lbd=lbd,
                Ptb=Ptb,
                gamma=gamma)


    optimizer = optim.Adam(model.parameters(),
                           lr=lr,
                           weight_decay=5e-4)
    def train(epoch):
        t = time.time()
        model.train()
        optimizer.zero_grad()
        output = model(ft, adj)
        if "tagged" in dataset:
            loss_train = F.nll_loss(output[idx_train], labels[idx_train], weight=torch.Tensor([1, 1]))
        else:
            loss_train = F.nll_loss(output[idx_train], labels[idx_train])
        loss_train.backward()
        optimizer.step()

        model.eval()
        output = model(ft, adj)

        if "tagged" in dataset:
            weight_label = torch.Tensor([1, 1.5])
            loss_train = F.nll_loss(output[idx_train], labels[idx_train], weight=weight_label)
        else:
            loss_train = F.nll_loss(output[idx_train], labels[idx_train])
        acc_train = accuracy(output[idx_train], labels[idx_train])

        if "tagged" in dataset:
            loss_val = F.nll_loss(output[idx_val], labels[idx_val], weight=weight_label)
        else:
            loss_val = F.nll_loss(output[idx_val], labels[idx_val])
        acc_val = accuracy(output[idx_val], labels[idx_val])
        print('Epoch: {:04d}'.format(epoch + 1),
              'loss_train: {:.4f}'.format(loss_train.data.item()),
              'acc_train: {:.4f}'.format(acc_train.data.item()),
              'loss_val: {:.4f}'.format(loss_val.data.item()),
              'acc_val: {:.4f}'.format(acc_val.data.item()),
              'time: {:.4f}s'.format(time.time() - t))

        return loss_val.data.item()

    loss_values = []
    bad_counter = 0
    best = epochs + 1
    best_epoch = 0
    for epoch in range(epochs):
        optimizer.zero_grad()
        loss_values.append(train(epoch))

        torch.save(model.state_dict(), 'gcn/{}.pkl'.format(epoch))
        if loss_values[-1] < best:
            best = loss_values[-1]
            best_epoch = epoch
            bad_counter = 0
        else:
            bad_counter += 1

        if bad_counter == patience:
            break

        files = glob.glob('gcn/[0-9]*.pkl')
        for file in files:
            file = file.replace('\\', '/')
            epoch_nb = int(file.split('.')[0].split('/')[1])
            if epoch_nb < best_epoch:
                os.remove(file)

    files = glob.glob('gcn/[0-9]*.pkl')
    for file in files:
        file = file.replace('\\', '/')
        epoch_nb = int(file.split('.')[0].split('/')[1])
        if epoch_nb > best_epoch:
            os.remove(file)

    def compute_test():
        model.eval()
        output = model(ft, adj)
        loss_test = F.nll_loss(output[idx_test], labels[idx_test])
        acc_test = accuracy(output[idx_test], labels[idx_test])
        print("Test set results:",
              "loss= {:.4f}".format(loss_test.data.item()),
              "accuracy= {:.4f}".format(acc_test.data.item()))

    def compute_acc_group():
        model.eval()
        output = model(ft, adj)
        acc_train = accuracy(output[idx_train], labels[idx_train])
        acc_test = accuracy(output[idx_test], labels[idx_test])
        if len(gender) == 0:
            acc_train1 = acc_train2 = acc_train
            acc_test1 = acc_test2 = acc_test
        else:
            if torch.is_tensor(gender):
                gender_train = gender[idx_train]
                gender_test = gender[idx_test]
            else:
                gender_train = torch.Tensor(gender)[idx_train]
                gender_test = torch.Tensor(gender)[idx_test]

            idx_train_1 = idx_train[gender_train == 1]
            idx_train_2 = idx_train[gender_train == 2]
            acc_train1, acc_train2 = accuracy(output[idx_train_1], labels[idx_train_1]), accuracy(output[idx_train_2],
                                                                                                  labels[idx_train_2])

            idx_test_1 = idx_test[gender_test == 1]
            idx_test_2 = idx_test[gender_test == 2]
            acc_test1, acc_test2 = accuracy(output[idx_test_1], labels[idx_test_1]), accuracy(output[idx_test_2],
                                                                                              labels[idx_test_2])

        return [acc_train.detach().item(), acc_train1.detach().item(), acc_train2.detach().item(),
                acc_test.detach().item(), acc_test1.detach().item(), acc_test2.detach().item()]

    compute_test()
    acc_list = compute_acc_group()

    oh_label = one_hot_trans(labels)
    print("p1 = {} and p2 = {}!".format(model.ptb_adj.p1, model.ptb_adj.p2))

    outputs = model(ft, adj)
    print(np.unique(outputs.argmax(axis=1), return_counts=True))
    if outputs.shape[1] == 2:
        preds = outputs.argmax(axis=1)
        acc = accuracy_score(preds, labels)
        prec = precision_score(labels, preds)
        recall = recall_score(labels, preds)

        print("Accuracy = {:.2%}, Precision={:.2%}, Recall = {:.2%}".format(acc, prec, recall))

    if not os.path.exists(saving_path):
        os.makedirs(saving_path)
    '''all_results = [ft, labels, outputs, adj, gender]

    with open('{}/{}_gcn_target.pkl'.format(saving_path, dataset), 'wb') as f:
        pkl.dump(all_results, f)
'''
    with open('{}/{}_gcn_acc.pkl'.format(saving_path, dataset), 'wb') as f:
        pkl.dump(acc_list, f)

    with open('{}/ind.{}.allx'.format(saving_path, dataset), 'wb') as f:
        pkl.dump(ft, f)

    with open('{}/ind.{}.ally'.format(saving_path, dataset), 'wb') as f:
        pkl.dump(oh_label, f)

    with open('{}/{}_gcn_pred.pkl'.format(saving_path, dataset), 'wb') as f:
        pkl.dump(outputs, f)

    '''with open('{}/ind.{}.adj'.format(saving_path, dataset), 'wb') as f:
        pkl.dump(1 * (adj > 0), f)'''

    with open('{}/ind.{}.gender'.format(saving_path, dataset), 'wb') as f:
        pkl.dump(gender, f)
    if not DP:
        lbd = 0
    if not Ptb:
        gamma = -1

    return np.array([lbd, gamma] + acc_list)

if __name__ == "__main__":
    datapath = "dataset/"
    dataset = "pokec"
    ego_user = "107"
    adj, ft, gender, labels = load_data(datapath, dataset, ego_user, dropout=0)
    delta = 0.1
    if delta > 0:
        adj = pkl.load(open("{}/CNR/Group/Reduce/Delta={}/ind.{}.adj".format("gcn", delta, dataset), "rb"))
    acc_lists = []
    for gamma in [10.0, 5.0, 3.0, 1.0, 0.5]:
        for t in range(5):
            tmp_list = [0, 0, 0, 0]
            count = 0
            while tmp_list[-4] < 0.2 and count < 5:
                count += 1
                print("Try {} time for beta={}".format(count, gamma))
                tmp_list = run_GCN(gender, ft, adj, labels, epochs=300, dataset=dataset,
                                   DP=False, lbd=0,
                                   Ptb=True, gamma=gamma,
                                   saving_path="gcn/ptb_adj/gamma={}/t={}".format(gamma, t))
            if tmp_list[-4] > 0.2:
                acc_lists.append(tmp_list)
            else:
                print("Target model with Ptb failed for gamma={} and t={} for {} times".format(gamma, t, count))


    acc_lists = np.array(acc_lists)
    df_acc = pd.DataFrame(acc_lists, columns=["Beta", "Gamma", "train acc", "train acc 1", "train acc 2",
                                              "test acc", "test acc 1", "test acc 2"])
    df_acc_avg = df_acc.groupby(["Beta", "Gamma"]).mean()
    df_acc_avg.to_csv("gcn/ptb_adj/{}_target_acc_agg.csv".format(dataset))
    pass