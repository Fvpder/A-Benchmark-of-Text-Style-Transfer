import os, sys
import torch
import argparse
from nltk.translate.bleu_score import corpus_bleu
from nltk.tokenize import word_tokenize
sys.path.append(".")
from utils.dataset import LABEL_MAP, read_file
from utils.setting import DATA_DIR, BASE_DIR


def prepare_data(args):
    labels = LABEL_MAP[args.dataset]
#prepare the training data
    for mode in ["train", "dev", "test"]:
        with open('{}.txt'.format(mode),'w') as f3:
            for label in labels:
                with open(os.path.join(args.data_dir, "{}.{}".format(mode, label)),'r') as f1:
                    f3.writelines(f1.readlines())


class Evaluator:
    def __init__(self, args, device="cpu"):
        self.dataset = args.dataset
        self.data_dir = args.datadir
        self.device = device


    def get_data(self, label, file_name="test"):
        data = []
        label_data = read_file(os.path.join(self.data_dir, "{}.{}".format(file_name, label)))
        data += [[word_tokenize(sent)] for sent in label_data]
        return data

    def adding_multiple_references(self, label):
        human_reference_path = f"{self.data_dir}/references/"
        multi_candidate_list = []
        if self.dataset in ["yelp"]:
            ref_num = 4
            file_list_0 = ["reference0.0", "reference1.0", "reference2.0", "reference3.0"]
            file_list_1 = ["reference0.1", "reference1.1", "reference2.1", "reference3.1"]
        elif self.dataset in ["gyafc_fr", "gyafc_em"]:
            ref_num = 4
            file_list_0 = ["ref.formal.0", "ref.formal.1", "ref.formal.2", "ref.formal.3"]
            file_list_1 = ["ref.informal.0", "ref.informal.1", "ref.informal.2", "ref.informal.3"]

        if label==0:
            fp_list = [open(human_reference_path + str(i), encoding="utf-8").readlines() for i in file_list_0]
            for i in range(len(fp_list[0])):
                multi_candidate_list.append([word_tokenize(fp_list[j][i].lower()) for j in range(ref_num)])
        else:
            fp_list = [open(human_reference_path + str(i), encoding="utf-8").readlines() for i in file_list_1]
            for i in range(len(fp_list[0])):
                multi_candidate_list.append([word_tokenize(fp_list[j][i].lower()) for j in range(ref_num)])

        return multi_candidate_list

    def get_ref_bleu(self, seg_sents, ref_data):
        try:
            assert len(seg_sents) == len(ref_data)
        except:
            print(len(seg_sents))
        return corpus_bleu(ref_data, seg_sents)

    def get_self_bleu(self, seg_sents, ori_data):
        try:
            assert len(seg_sents) == len(ori_data)
        except:
            print(len(seg_sents))
        return corpus_bleu(ori_data, seg_sents)


    def evaluate_file(self, result_file, hasref, multiref):
        ref_bleu = None
        multi_rfbl = None
        transfered_sents = []
        labels = []

        i = int(result_file[-1])
        sents = read_file(result_file)
        transfered_sents += sents
        labels += [i] * len(sents)
        ori_data = self.get_data(file_name="test", label=i)
        seg_sents = [word_tokenize(sent) for sent in transfered_sents]
        self_bleu = self.get_self_bleu(seg_sents, ori_data)

        if hasref:
            ref_data = self.get_data(file_name="reference", label=i)
            ref_bleu = self.get_ref_bleu(seg_sents, ref_data)
        if multiref:
            multi_ref = self.adding_multiple_references(label=i)
            multi_rfbl = self.get_ref_bleu(seg_sents, multi_ref)

        return self_bleu, ref_bleu, multi_rfbl

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=str, default="gyafc_em")
    parser.add_argument('--algorithm', type=str, default="chatgpt_fs")
    parser.add_argument('--datadir', type=str, default="./data/gyafc_fr")
    parser.add_argument('--outdir', type=str, default="outputs/chatgpt/gyafc_em/promptv2.1")
    parser.add_argument('--cpu', action='store', default=False)
    parser.add_argument('--file', type=str, default="all", help='')
    parser.add_argument('--hasref', action='store_true', default=False)
    parser.add_argument('--multiref', action='store_true', default=False)
    args = parser.parse_args()

    args.datadir = f'{DATA_DIR}/{args.dataset}'
    if not os.path.exists(f'{BASE_DIR}/eval_out/{args.algorithm}'):
        os.mkdir(f'{BASE_DIR}/eval_out/{args.algorithm}')

    if args.file == "all":
        result_files = set()
        for file in os.listdir(f'{BASE_DIR}/{args.outdir}'):
            file_split = file.split(".")
            if len(file_split) == 2 and file_split[0] != "log":
                result_files.add(os.path.join(BASE_DIR, args.outdir, file))
        result_files = sorted(list(result_files))
    else:
        result_files = [args.file]

    if args.dataset in ["yelp", "gyafc_fr", "gyafc_em"]:
        args.hasref = True
        args.multiref = True
    elif args.dataset in ["shakespeare", "amazon", "styleptb_ARR", "styleptb_TFU"]:
        args.hasref = True
        args.multiref = False

    device = "cuda" if not args.cpu and torch.cuda.is_available() else "cpu"
    evaluator = Evaluator(args, device=device)
    for result_file in result_files:
        # print(result_file, end="\t")
        self_bleu, ref_bleu, multibleu = evaluator.evaluate_file(result_file, hasref=args.hasref, multiref=args.multiref)
        eval_path = f'{BASE_DIR}/eval_out/{args.algorithm}/{args.dataset}/{result_file.split("/")[-2]}'
        if not os.path.exists(eval_path):
            os.mkdir(eval_path)
        with open(f'{eval_path}/gen{result_file.split("/")[-1].split(".")[1]}.txt', 'a') as fin:
            fin.write(f'{self_bleu}\n{ref_bleu}\n{multibleu}\n')
        # print(f'self_bleu:{self_bleu}, ref_bleu:{ref_bleu}\t')
