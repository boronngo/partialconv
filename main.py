from comet_ml import Experiment

import torch
from torchvision import transforms
from torch.utils.data import DataLoader

from src.config import get_config
from src.dataset import Places2
from src.model import PConvUNet
from src.loss import InpaintingLoss, VGG16FeatureExtractor
from src.train import Trainer
from src.utils import Config, load_ckpt


# set the config
config = Config(get_config())

# Define the used device
device = torch.device('cuda:{}'.format(config.cuda_id)
                      if torch.cuda.is_available() else 'cpu')

# Define the model
model = PConvUNet(layer_size=config.layer_size).to(device)

# Data Transformation
img_tf = transforms.ToTensor()
mask_tf = transforms.ToTensor()

# Define the Validation set
dataset_val = Places2(config.img_root,
                      config.mask_root,
                      img_tf,
                      mask_tf,
                      data='val')

# Set the configuration for training
if config.mode == 'train':
    # set the comet-ml
    if config.comet:
        experiment = Experiment(api_key=config.api_key,
                                project_name=config.project_name,
                                workspace=config.workspace)
        experiment.log_parameters(config)
    else:
        experiment = None

    # Define the Places2 Dataset and Data Loader
    dataset_train = Places2(config.img_root,
                            config.mask_root,
                            img_tf,
                            mask_tf,
                            data='train')

    # Define the Loss fucntion
    criterion = InpaintingLoss(VGG16FeatureExtractor()).to(device)
    # Define the Optimizer
    lr = config.finetune_lr if config.finetune else config.initial_lr
    if config.optim == 'Adam':
        optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()),
                                     lr=lr,
                                     weight_decay=config.weight_decay)
    elif config.optim == 'SGD':
        optimizer = torch.optim.SGD(filter(lambda p: p.requires_grad, model.parameters()),
                                    lr=lr,
                                    momentum=config.momentum,
                                    weight_decay=config.weight_decay)

    start_iter = 0
    if config.resume:
        start_iter = load_ckpt(config.resume,
                               [('model', model)],
                               [('optimizer', optimizer)])
        for param_group in optimizer.param_groups:
            param_group['lr'] = lr
        print('Starting from iter ', start_iter)

    trainer = Trainer(start_iter, config, device, model, dataset_train,
                      dataset_val, criterion, optimizer, experiment=experiment)
    if config.comet:
        with experiment.train():
            trainer.iterate(config.num_iter)
    else:
        trainer.iterate(config.num_iter)

# Set the configuration for testing
elif config.mode == 'test':
    # <model load the trained weights>
    evaluate(model, dataset_val)

