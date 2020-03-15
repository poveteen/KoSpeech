"""
Copyright 2020- Kai.Lib
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
      http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os
import queue
import torch
from package.dataset import BaseDataset
from package.definition import *
from package.hparams import HyperParams
from package.loader import BaseDataLoader, load_data_list, load_targets
from package.utils import get_distance


def test(model, queue, device):
    """ Test for Model Performance """
    logger.info('test() start')
    total_dist = 0
    total_length = 0
    total_sent_num = 0

    model.eval()

    with torch.no_grad():
        while True:
            feats, targets, feat_lengths, script_lengths = queue.get()
            if feats.shape[0] == 0:
                break

            feats = feats.to(device)
            targets = targets.to(device)
            target = targets[:, 1:]

            model.module.flatten_parameters()
            y_hat, _ = model(
                feats = feats,
                targets = targets,
                teacher_forcing_ratio = 0.0,
                use_beam_search = True
            )
            dist, length = get_distance(target, y_hat, id2char, EOS_TOKEN)
            total_dist += dist
            total_length += length
            total_sent_num += target.size(0)

    CER = total_dist / total_length
    logger.info('test() completed')
    return CER

if __name__ == '__main__':
    os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
    logger.info("device : %s" % torch.cuda.get_device_name(0))
    logger.info("CUDA is available : %s" % (torch.cuda.is_available()))
    logger.info("CUDA version : %s" % (torch.version.cuda))
    logger.info("PyTorch version : %s" % (torch.__version__))

    hparams = HyperParams()
    hparams.logger_hparams()
    cuda = hparams.use_cuda and torch.cuda.is_available()
    device = torch.device('cuda' if cuda else 'cpu')
    model = torch.load("model.pt")
    model.module.set_beam_size(k = 8)
    audio_paths, label_paths = load_data_list(data_list_path=TEST_LIST_PATH, dataset_path=DATASET_PATH)

    target_dict = load_targets(label_paths)
    logger.info('start')

    test_dataset = BaseDataset(
        audio_paths = audio_paths,
        label_paths = label_paths,
        sos_id = SOS_TOKEN,
        eos_id = EOS_TOKEN,
        target_dict = target_dict,
        input_reverse = hparams.input_reverse,
        use_augment = False,
        pack_by_length = False
    )

    test_queue = queue.Queue(hparams.worker_num << 1)
    test_loader = BaseDataLoader(test_dataset, test_queue, hparams.batch_size, 0)
    test_loader.start()

    CER = test(model, test_queue, device)
    logger.info('20h Test Set CER : %s' % CER)