import abc
import os
from pathlib import Path
import sys

import torch

from tools import dict_to_numpy

PROJECT_ROOT = Path(__file__).resolve().parent
DMVFN_ROOT = PROJECT_ROOT / "vp_models" / "dmvfn"
if str(DMVFN_ROOT) not in sys.path:
    sys.path.insert(0, str(DMVFN_ROOT))

from vp_models.dmvfn.model.model import Model


class VideoPredictionModel(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __call__(self, batch):
        raise NotImplementedError

    def format_model_epoch_filename(self, epoch):
        raise NotImplementedError

    def get_checkpoint_file(self, checkpoint_dir, model_epoch):
        checkpoint_dir = str(Path(checkpoint_dir).expanduser().resolve())
        if model_epoch is not None:
            if os.path.isfile(checkpoint_dir):
                checkpoint_dir = os.path.dirname(checkpoint_dir)
            checkpoint_file = os.path.join(
                checkpoint_dir, self.format_model_epoch_filename(model_epoch)
            )
        else:
            checkpoint_file = checkpoint_dir
        return checkpoint_file

    def close(self):
        pass


class DMVFNActModel(VideoPredictionModel):
    def __init__(
        self,
        checkpoint_file,
        n_past,
        action_dim=2,
        max_batch_size=800,
        epoch=None,
        device=None,
    ):
        self.checkpoint_file = checkpoint_file
        self.device = device or ("cuda:0" if torch.cuda.is_available() else "cpu")
        self.model = Model(local_rank=0, load_path=self.checkpoint_file, training=False, device=self.device)
        self.num_context = n_past
        self.max_batch_size = max_batch_size
        self.base_prediction_modality = "rgb"
        self.inner_bs = 10

    def prepare_batch(self, xs):
        keys = ["video", "actions"]
        xs["video"] = xs["video"] / 255.0

        batch = {
            k: torch.from_numpy(x).to(self.device, non_blocking=True).float()
            for k, x in xs.items()
            if k in keys
        }
        batch["video"] = torch.permute(batch["video"], (0, 1, 4, 2, 3))[:, :, [2, 1, 0], :, :]
        return batch

    def __call__(self, batch, grad_enabled=False, scale_list=None):
        if scale_list is None:
            scale_list = [4, 4, 4, 2, 2, 2, 1, 1, 1]

        preds = []
        batch = self.prepare_batch(batch)
        imgs = batch["video"]
        actions = batch["actions"]
        img0, img1 = imgs[:, 0], imgs[:, 1]
        img0 = img0[:, [2, 1, 0], :, :]
        img1 = img1[:, [2, 1, 0], :, :]
        batch_size, _, channels, height, width = imgs.shape

        action0, action1 = actions[:, 0], actions[:, 1]
        action0 = action0.unsqueeze(2).unsqueeze(3).repeat(1, 1, height, width)
        action1 = action1.unsqueeze(2).unsqueeze(3).repeat(1, 1, height, width)

        pred_len = actions.shape[1] - 1
        for i in range(pred_len):
            inner_pred = []
            for start in range(0, batch_size, self.inner_bs):
                end = min(start + self.inner_bs, batch_size)
                with torch.no_grad():
                    merged = self.model.dmvfn(
                        torch.cat((img0[start:end], img1[start:end]), 1),
                        scale=scale_list,
                        actions=[action0[start:end], action1[start:end]],
                        training=False,
                    )
                inner_pred.append(merged[-1] if merged else img0[start:end])

            pred = torch.cat(inner_pred, dim=0).reshape(batch_size, channels, height, width)
            preds.append(pred)
            img0 = img1
            img1 = pred

            if i != pred_len - 1:
                action0 = action1
                action1 = actions[:, 2 + i].unsqueeze(2).unsqueeze(3).repeat(1, 1, height, width)

        preds.append(preds[-1])
        preds = {
            "rgb": torch.stack(preds, 1).permute(0, 1, 3, 4, 2)[:, :, :, :, [2, 1, 0]]
        }
        return dict_to_numpy(preds)
