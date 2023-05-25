import os

from GCN_dense import train_model
from utils import *
from stealing_link.partial_graph_generation import get_partial
from attack import attack_main
import argparse
import json
from run_target import run_target
import math

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_type', type=str, default="GAT", help='Model Type, GAT or gcn')
    parser.add_argument('--dataset', type=str, default="facebook", help='dataset, facebook or cora')
    parser.add_argument('--shadow_dataset', type=str, default="cora", help='shadow dataset, cora')
    parser.add_argument('--ego_user', type=str, default="107", help='ego user of target dataset')
    parser.add_argument('--datapath', type=str, default="dataset/", help='datapath for original data')
    parser.add_argument('--epoch', type=int, default=300, help='number of epoch')
    parser.add_argument('--lbd', type=float, default=0, help='lambda for baseline')
    parser.add_argument('--gamma', type=float, default=math.inf, help='gamma for M-IN')
    parser.add_argument('--ep', type=float, default=0, help='epsilon for conventional DP')
    parser.add_argument('--DP', action="store_true", default=False,
                        help='True if baseline experiment is running')
    parser.add_argument('--Ptb', action="store_true", default=False,
                        help='True if M-In experiment is running.')
    parser.add_argument('--Ptb_sq', action="store_true", default=False,
                        help='True if M-In-sq experiment is running.')
    parser.add_argument('--density_change', action="store_true", default=False,
                        help='True if use density modified graph.')
    parser.add_argument('--fair_adj', action="store_true", default=False,
                        help='True if run with M-Pre.')

    parser.add_argument('--run_dense', action="store_true", default=False, help='True if dense experiment is required.')
    parser.add_argument('--fair_sample', action="store_true", default=False,
                        help='True if fair sample for MIA is required')
    parser.add_argument('--run_attack', action="store_true", default=False,
                        help='True if attack experiment is required.')
    parser.add_argument('--prepare_new', action="store_true", default=False,
                        help='True if prepare new attack input files')
    parser.add_argument('--run_Target', action="store_true", default=False,
                        help='True if Target experiment is required.')
    parser.add_argument('--run_partial', action="store_true", default=False,
                        help='True if new partial data is required.')
    parser.add_argument('--null_model', action="store_true", default=False,
                        help='True if run null_model experiment')
    parser.add_argument('--DP_con', action="store_true", default=False,
                        help='True if run conventional DP experiment')
    parser.add_argument('--arr', action="store_true", default=False,
                        help='True if run ARR experiment')
    parser.add_argument('--ptb_time', type=float, default=-1,
                        help='positive if only one time ptb')

    args = parser.parse_args()

    model_type = args.model_type  # "gcn"
    dataset = args.dataset  # "cora"
    shadow_dataset = args.shadow_dataset  # "cora"
    ego_user = args.ego_user  # "107"
    datapath = args.datapath  # "dataset/"
    epoch = args.epoch  # 300
    lbd = args.lbd
    gamma = args.gamma
    DP = args.DP
    Ptb = args.Ptb
    Ptb_sq = args.Ptb_sq
    null_model = args.null_model
    DP_con = args.DP_con
    ep = args.ep
    arr = args.arr
    dst = args.density_change
    fair_lp = args.fair_adj

    run_dense = args.run_dense  # False
    fair_sample = args.fair_sample  # False
    run_attack = args.run_attack  # False
    prepare_new = args.prepare_new  # True
    run_Target = args.run_Target  # False
    run_partial = args.run_partial  # True

    with open('model_config.json', 'r') as f:
        config = json.load(f)[dataset][model_type]
    delta = config["delta"]
    adj, ft, gender, labels = load_data(datapath, dataset, ego_user, dropout=0)

    MIA_res_addon = ""
    if delta > 0:
        adj = pkl.load(open(config["adj_location"], "rb"))
        MIA_res_addon = "CNR/Group/Reduce/Delta={}/".format(delta)

    if dst:
        print("load density-changed adj: "+ config['density_adj_loc'])
        adj = pkl.load(open(config['density_adj_loc'], "rb"))

    if run_dense:
        train_model(gender, ft, adj, labels, dataset, num_epoch=epoch, model_type="dense", saving_path="dense")

    if not DP and not Ptb:
        target_saving_path = model_type
        partial_path = config["partial_path"]
        attack_res_loc = model_type
    elif DP:
        target_saving_path = model_type + "/baseline/lbd={}".format(lbd)
        partial_path = config["partial_path"] + "baseline/lbd={}/".format(lbd)
        attack_res_loc = model_type + "/baseline/lbd={}".format(lbd)
    else:
        target_saving_path = model_type + "/M_IN/gamma={}".format(gamma).replace("M_IN", "M_IN(once)" if args.ptb_time==1 else "M_IN").replace("M_IN", "M_IN(multi)" if args.ptb_time==2 else "M_IN")
        partial_path = config["partial_path"] + "M_IN/gamma={}/".format(gamma).replace("M_IN", "M_IN(once)" if args.ptb_time else "M_IN").replace("M_IN", "M_IN(multi)" if args.ptb_time==2 else "M_IN")
        attack_res_loc = model_type + "/M_IN/gamma={}".format(gamma).replace("M_IN", "M_IN(once)" if args.ptb_time else "M_IN").replace("M_IN", "M_IN(multi)" if args.ptb_time==2 else "M_IN")
    if arr:
        target_saving_path = model_type + "/ARR/epsilon={}".format(ep)
        partial_path = config["partial_path"] + "ARR/epsilon={}/".format(ep)
        attack_res_loc = model_type + "/ARR/epsilon={}".format(ep)

    if DP_con:
        target_saving_path = model_type + "/DP_con/ep={}_bs={}".format(ep, 100 if model_type == "GAT" else 20)
        partial_path = model_type + "/DP_con/ep={}/".format(ep)
        attack_res_loc = model_type + "/DP_con/ep={}".format(ep)

    if dst and not Ptb and not arr and not DP_con:
        print("density changed with no defense")
        target_saving_path = config["dst_partial_path"]
        partial_path = config["dst_partial_path"]
        attack_res_loc = config["dst_partial_path"]
    elif dst and Ptb:
        target_saving_path = config["dst_partial_path"] + "M_IN/gamma={}/".format(gamma)
        partial_path = config["dst_partial_path"] + "M_IN/gamma={}/".format(gamma)
        attack_res_loc = config["dst_partial_path"] + "/M_IN/gamma={}".format(gamma)
    elif dst and arr:
        target_saving_path = config["dst_partial_path"] + 'ARR/epsilon={}'.format(ep)
        partial_path = config["dst_partial_path"] + "ARR/epsilon={}/".format(ep)
        attack_res_loc =config["dst_partial_path"] + "/ARR/epsilon={}".format(ep)
    elif DP_con and dst:
        target_saving_path = config["dst_partial_path"] + "/DP_con/ep={}_bs={}".format(ep, 100 if model_type == "GAT" else 20)
        partial_path = config["dst_partial_path"] + "/DP_con/ep={}/".format(ep)
        attack_res_loc = config["dst_partial_path"] + "/DP_con/ep={}".format(ep)

    if null_model:
        target_saving_path = "Null_model"
        partial_path = "Null_model/{}/".format(model_type)
        attack_res_loc = "Null_model/" + model_type

    if fair_lp:
        print("Running fair_LP")
        #adj = pkl.load(open(model_type + "/fair_adj/ind.{}.adj".format(dataset), "rb"))
        target_saving_path = model_type + "/M_pre/"
        partial_path = config["partial_path"] + "/M_pre/"
        attack_res_loc = model_type + "/M_pre"

    for locs in [target_saving_path, partial_path, attack_res_loc]:
        if not os.path.exists(locs):
            os.makedirs(locs)

    if run_Target:
        run_target(model_type, config, gender, ft, adj, labels,
                   DP=DP, lbd=lbd, Ptb=Ptb, gamma=gamma,
                   epochs=epoch, dataset=dataset, saving_path=target_saving_path,
                   null_model=null_model, ARR=arr, epsilon=ep, mpre=fair_lp, ptb_sq=Ptb_sq, ptb_time=args.ptb_time)

    df_acc = []
    partial_done = False
    agg_all = []
    for at in [3, 6]:
        a_all, p_all, r_all, roc_all = 0, 0, 0, 0
        for t in range(5):
            if run_partial and not partial_done:
                get_partial(adj=adj, model_type=model_type, datapath=config["datapath"], pred_path=target_saving_path,
                            partial_path=partial_path,
                            dataset=dataset, fair_sample=fair_sample, t=t)
            if not run_attack:
                continue
            print("Start Attack {} with {} balanced sample for {} time.".format(at, fair_sample, t))
            a, p, r, roc, acc_list = attack_main(datapath=config["partial_path"],
                                                 dataset=dataset,
                                                 saving_path=partial_path,
                                                 ratio=0.2,
                                                 attack_type=at,
                                                 fair_sample=fair_sample,
                                                 t=t)
            df_acc.append(acc_list)
            a_all += a
            p_all += p
            r_all += r
            roc_all += roc
        partial_done = True
        print("Average Performance of attack {} on model {} over {} time:\n" \
              " Accuracy = {},\n"
              " Precision={},\n"
              " Recall = {},\n"
              " ROC={}".format(at,
                               model_type,
                               t + 1,
                               a_all / (t + 1),
                               p_all / (t + 1),
                               r_all / (t + 1),
                               roc_all / (t + 1)))
        agg_all.append([at, a_all / (t + 1), p_all / (t + 1), r_all / (t + 1), roc_all / (t + 1)])

    df_acc = pd.DataFrame(df_acc, columns=["Attack",
                                           "Acc_train", "Acc_train1", "Acc_train2", "Acc_train0",
                                           "Acc_test", "Acc_test1", "Acc_test2", "Acc_test0"])
    df_acc_agg = df_acc.groupby("Attack").mean()
    df_agg_performance = pd.DataFrame(agg_all, columns=["Attack Type", "Accuracy", "Precision", "Recall", "AUC"])

    if run_attack:
        df_acc_agg.to_csv(
            "{}/MIA_res/{}_attack{}acc_agg.csv".format(attack_res_loc, dataset, "_fair_" if fair_sample else "_"))
        df_acc.to_csv(
            "{}/MIA_res/{}_attack{}acc.csv".format(attack_res_loc, dataset, "_fair_" if fair_sample else "_"))
        df_agg_performance.to_csv(
            "{}/MIA_res/{}_attack{}performance.csv".format(attack_res_loc, dataset, "_fair_" if fair_sample else "_"))
