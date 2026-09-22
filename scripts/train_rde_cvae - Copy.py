
"""
RDE CVAE Complete Pipeline v2.0
Single-file solution: Model + Dataset + Training + Generation

FIXES:
- Exact decoder output_padding for 150x300 output
- No BatchNorm1d (batch_size=1 safe)
- CUDA auto-detection with fallback
- Consolidated: no separate model file needed

Usage:
    python rde_cvae_complete.py --mode train --epochs 500
    python rde_cvae_complete.py --mode generate --num_cases 60
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pandas as pd
import json
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# =============================================================================
# DEVICE SETUP
# =============================================================================

def get_device():
    """Auto-detect best available device."""
    if torch.cuda.is_available():
        device = torch.device('cuda')
        print(f"GPU detected: {torch.cuda.get_device_name(0)}")
        print(f"CUDA version: {torch.version.cuda}")
        print(f"PyTorch CUDA: {torch.backends.cuda.is_built()}")
        return device
    else:
        print("WARNING: CUDA not available, using CPU")
        print("To fix: conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia")
        return torch.device('cpu')

# =============================================================================
# MODEL ARCHITECTURE
# =============================================================================

class SpatialEncoder(nn.Module):
    def __init__(self, in_channels=6, spatial_dim=128):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, 32, 4, 2, 1),  # 300x150 -> 150x75
            nn.BatchNorm2d(32),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(32, 64, 4, 2, 1),           # 150x75 -> 75x37
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(64, 128, 4, 2, 1),          # 75x37 -> 37x18
            nn.BatchNorm2d(128),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(128, 256, 4, 2, 1),         # 37x18 -> 18x9
            nn.BatchNorm2d(256),
            nn.LeakyReLU(0.2, inplace=True),
        )
        self.fc = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(256, spatial_dim),
            nn.LeakyReLU(0.2, inplace=True)
        )

    def forward(self, x):
        return self.fc(self.conv(x))


class TemporalEncoder(nn.Module):
    def __init__(self, input_dim=128, hidden_dim=128, num_layers=2, dropout=0.1):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0
        )

    def forward(self, x):
        output, (hidden, cell) = self.lstm(x)
        return output, hidden


class ConditionalVAE(nn.Module):
    def __init__(self, latent_dim=64, temporal_dim=256, condition_dim=4, hidden_dim=256):
        super().__init__()
        self.latent_dim = latent_dim

        self.encoder = nn.Sequential(
            nn.Linear(temporal_dim + condition_dim, hidden_dim),
            nn.LeakyReLU(0.2),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LeakyReLU(0.2),
        )
        self.fc_mu = nn.Linear(hidden_dim, latent_dim)
        self.fc_logvar = nn.Linear(hidden_dim, latent_dim)

        self.decoder = nn.Sequential(
            nn.Linear(latent_dim + condition_dim, hidden_dim),
            nn.LeakyReLU(0.2),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LeakyReLU(0.2),
            nn.Linear(hidden_dim, temporal_dim),
        )

    def encode(self, temporal_features, condition):
        x = torch.cat([temporal_features, condition], dim=-1)
        h = self.encoder(x)
        return self.fc_mu(h), self.fc_logvar(h)

    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z, condition):
        x = torch.cat([z, condition], dim=-1)
        return self.decoder(x)

    def forward(self, temporal_features, condition):
        mu, logvar = self.encode(temporal_features, condition)
        z = self.reparameterize(mu, logvar)
        return self.decode(z, condition), mu, logvar


class SpatialDecoder(nn.Module):
    """Decoder with EXACT output_padding for 150x300 output."""

    def __init__(self, spatial_dim=128, out_channels=6):
        super().__init__()

        self.fc = nn.Sequential(
            nn.Linear(spatial_dim, 256 * 9 * 18),
            nn.LeakyReLU(0.2)
        )

        # Exact inverse of encoder with correct output_padding:
        # 18x9 -> 37x18 (w_op=1, h_op=0)
        # 37x18 -> 75x37 (w_op=1, h_op=1)
        # 75x37 -> 150x75 (w_op=0, h_op=1)
        # 150x75 -> 300x150 (w_op=0, h_op=0)

        self.deconv = nn.Sequential(
            # Block 1: 18x9 -> 37x18
            nn.ConvTranspose2d(256, 128, 4, 2, 1, output_padding=(0, 1)),
            nn.BatchNorm2d(128),
            nn.LeakyReLU(0.2, inplace=True),

            # Block 2: 37x18 -> 75x37
            nn.ConvTranspose2d(128, 64, 4, 2, 1, output_padding=(1, 1)),
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.2, inplace=True),

            # Block 3: 75x37 -> 150x75
            nn.ConvTranspose2d(64, 32, 4, 2, 1, output_padding=(1, 0)),
            nn.BatchNorm2d(32),
            nn.LeakyReLU(0.2, inplace=True),

            # Block 4: 150x75 -> 300x150
            nn.ConvTranspose2d(32, out_channels, 4, 2, 1),
        )

    def forward(self, z_spatial):
        x = self.fc(z_spatial)
        x = x.view(-1, 256, 9, 18)
        return self.deconv(x)


class RDECVAEModel(nn.Module):
    def __init__(self, in_channels=6, spatial_dim=128, hidden_dim=128,
                 latent_dim=64, condition_dim=4, num_lstm_layers=2, dropout=0.1):
        super().__init__()

        self.spatial_dim = spatial_dim
        self.hidden_dim = hidden_dim
        self.temporal_dim = 2 * hidden_dim

        self.spatial_encoder = SpatialEncoder(in_channels, spatial_dim)
        self.temporal_encoder = TemporalEncoder(spatial_dim, hidden_dim, num_lstm_layers, dropout)
        self.cvae = ConditionalVAE(latent_dim, self.temporal_dim, condition_dim, hidden_dim)
        self.temporal_to_spatial = nn.Linear(self.temporal_dim, spatial_dim)
        self.spatial_decoder = SpatialDecoder(spatial_dim, in_channels)

        # No BatchNorm1d - causes crash with batch_size=1
        self.condition_norm = nn.Identity()

    def forward(self, fields, condition, return_latent=False):
        B, T, C, H, W = fields.shape

        # Spatial encoding per timestep
        spatial_latents = []
        for t in range(T):
            spatial_latents.append(self.spatial_encoder(fields[:, t]))
        spatial_latents = torch.stack(spatial_latents, dim=1)

        # Temporal encoding
        temporal_out, _ = self.temporal_encoder(spatial_latents)
        temporal_pooled = temporal_out[:, -1, :]

        # CVAE
        condition_norm = self.condition_norm(condition)
        recon_temporal, mu, logvar = self.cvae(temporal_pooled, condition_norm)

        # Decode each timestep
        recon_fields = []
        for t in range(T):
            z_t = recon_temporal + 0.1 * temporal_out[:, t, :]
            z_spatial = self.temporal_to_spatial(z_t)
            z_spatial = F.leaky_relu(z_spatial, 0.2)
            recon_fields.append(self.spatial_decoder(z_spatial))

        recon_fields = torch.stack(recon_fields, dim=1)

        if return_latent:
            z = self.cvae.reparameterize(mu, logvar)
            return recon_fields, mu, logvar, z
        return recon_fields, mu, logvar

    def generate(self, condition, num_timesteps=20, device='cuda'):
        if condition.ndim == 1:
            condition = condition.unsqueeze(0)
        condition = condition.to(device)
        B = condition.size(0)

        z = torch.randn(B, self.cvae.latent_dim).to(device)
        condition_norm = self.condition_norm(condition)
        temporal_features = self.cvae.decode(z, condition_norm)

        synthetic_fields = []
        for t in range(num_timesteps):
            t_norm = t / num_timesteps
            temporal_shift = torch.sin(torch.tensor(2 * np.pi * t_norm)).to(device)
            z_t = temporal_features + 0.1 * temporal_shift * torch.randn_like(temporal_features)

            z_spatial = self.temporal_to_spatial(z_t)
            z_spatial = F.leaky_relu(z_spatial, 0.2)
            synthetic_fields.append(self.spatial_decoder(z_spatial))

        return torch.stack(synthetic_fields, dim=1)


def vae_loss(recon_x, x, mu, logvar, kld_weight=0.001):
    recon_loss = F.mse_loss(recon_x, x, reduction='sum') / x.size(0)
    kld = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp()) / x.size(0)
    return recon_loss + kld_weight * kld, recon_loss, kld

# =============================================================================
# DATASET
# =============================================================================

class RDEDataset(Dataset):
    def __init__(self, npz_path, csv_path=None, normalize=True):
        data = np.load(npz_path)
        self.fields = data['fields']
        self.times = data['times']
        self.conditions = self._load_conditions(csv_path)

        self.n_cases = self.fields.shape[0]
        self.n_timesteps = self.fields.shape[1]

        self.normalize = normalize
        if normalize:
            self._compute_stats()
            self.fields = self._normalize_fields(self.fields)
            self.conditions = self._normalize_conditions(self.conditions)

    def _load_conditions(self, csv_path):
        if csv_path is None or not Path(csv_path).exists():
            return np.ones((self.n_cases, 4), dtype=np.float32)

        df = pd.read_csv(csv_path)
        cols = list(df.columns)

        case_col = next((c for c in ['case', 'case_id', 'Case'] if c in cols), cols[0])

        param_map = {}
        for std, candidates in {
            'phi': ['phi'], 'p0': ['p0_pa'], 'T0': ['T0_k'], 'cj': ['cantera_cj_speed_ms']
        }.items():
            for c in candidates:
                if c in cols:
                    param_map[std] = c
                    break

        conditions = []
        for case_name in sorted(df[case_col].unique()):
            case_df = df[df[case_col] == case_name]
            if len(case_df) == 0:
                continue
            row = case_df.iloc[0]
            conditions.append([
                float(row[param_map.get('phi', 'phi')]),
                float(row[param_map.get('p0', 'p0_pa')]),
                float(row[param_map.get('T0', 'T0_k')]),
                float(row[param_map.get('cj', 'cantera_cj_speed_ms')])
            ])

        return np.array(conditions, dtype=np.float32)

    def _compute_stats(self):
        self.field_mean = self.fields.mean(axis=(0, 1, 3, 4), keepdims=True)
        self.field_std = self.fields.std(axis=(0, 1, 3, 4), keepdims=True) + 1e-8
        self.cond_mean = self.conditions.mean(axis=0, keepdims=True)
        self.cond_std = self.conditions.std(axis=0, keepdims=True) + 1e-8

    def _normalize_fields(self, fields):
        return (fields - self.field_mean) / self.field_std

    def _denormalize_fields(self, fields):
        return fields * self.field_std + self.field_mean

    def _normalize_conditions(self, conditions):
        return (conditions - self.cond_mean) / self.cond_std

    def _denormalize_conditions(self, conditions):
        return conditions * self.cond_std + self.cond_mean

    def __len__(self):
        return self.n_cases

    def __getitem__(self, idx):
        return {
            'fields': torch.from_numpy(self.fields[idx]),
            'condition': torch.from_numpy(self.conditions[idx]),
            'case_id': idx
        }

# =============================================================================
# TRAINING
# =============================================================================

class EarlyStopping:
    def __init__(self, patience=20, min_delta=1e-4):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = None
        self.early_stop = False

    def __call__(self, val_loss):
        if self.best_loss is None:
            self.best_loss = val_loss
        elif val_loss > self.best_loss - self.min_delta:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
        else:
            self.best_loss = val_loss
            self.counter = 0


def train_epoch(model, dataloader, optimizer, device, kld_weight=0.001):
    model.train()
    total_loss = total_recon = total_kld = 0

    for batch in dataloader:
        fields = batch['fields'].to(device)
        condition = batch['condition'].to(device)

        optimizer.zero_grad()
        recon, mu, logvar = model(fields, condition)
        loss, recon_loss, kld = vae_loss(recon, fields, mu, logvar, kld_weight)

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        total_loss += loss.item()
        total_recon += recon_loss.item()
        total_kld += kld.item()

    n = len(dataloader)
    return total_loss / n, total_recon / n, total_kld / n


def validate(model, dataloader, device, kld_weight=0.001):
    model.eval()
    total_loss = total_recon = total_kld = 0

    with torch.no_grad():
        for batch in dataloader:
            fields = batch['fields'].to(device)
            condition = batch['condition'].to(device)

            recon, mu, logvar = model(fields, condition)
            loss, recon_loss, kld = vae_loss(recon, fields, mu, logvar, kld_weight)

            total_loss += loss.item()
            total_recon += recon_loss.item()
            total_kld += kld.item()

    n = len(dataloader)
    return total_loss / n, total_recon / n, total_kld / n


def plot_history(history, output_dir):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    for idx, (key, title) in enumerate([('loss', 'Total Loss'), ('recon', 'Reconstruction Loss'), ('kld', 'KL Divergence')]):
        axes[idx].plot(history[f'train_{key}'], label='Train')
        axes[idx].plot(history[f'val_{key}'], label='Val')
        axes[idx].set_title(title)
        axes[idx].set_xlabel('Epoch')
        axes[idx].legend()

    plt.tight_layout()
    plt.savefig(Path(output_dir) / 'training_history.png', dpi=150)
    plt.close()


def train(args):
    device = get_device()

    print(f"\nLoading dataset from {args.data}")
    dataset = RDEDataset(args.data, args.csv, normalize=True)
    print(f"Dataset: {len(dataset)} cases, {dataset.n_timesteps} timesteps")
    print(f"Field shape: {dataset.fields.shape}")
    print(f"Condition shape: {dataset.conditions.shape}")

    train_indices = list(range(0, 10))
    val_indices = list(range(10, 12))

    train_loader = DataLoader(torch.utils.data.Subset(dataset, train_indices),
                              batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(torch.utils.data.Subset(dataset, val_indices),
                            batch_size=args.batch_size, shuffle=False)

    model = RDECVAEModel(
        in_channels=6,
        spatial_dim=args.spatial_dim,
        hidden_dim=args.hidden_dim,
        latent_dim=args.latent_dim,
        condition_dim=4,
        num_lstm_layers=args.num_lstm_layers,
        dropout=args.dropout
    ).to(device)

    print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")

    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-5)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=10)

    early_stopping = EarlyStopping(patience=args.patience)
    best_val_loss = float('inf')
    history = {'train_loss': [], 'val_loss': [], 'train_recon': [], 'val_recon': [], 'train_kld': [], 'val_kld': []}

    print(f"\nStarting training for {args.epochs} epochs...")

    for epoch in range(args.epochs):
        train_loss, train_recon, train_kld = train_epoch(model, train_loader, optimizer, device, args.kld_weight)
        val_loss, val_recon, val_kld = validate(model, val_loader, device, args.kld_weight)

        scheduler.step(val_loss)

        for key, val in [('loss', train_loss), ('recon', train_recon), ('kld', train_kld)]:
            history[f'train_{key}'].append(val)
        for key, val in [('loss', val_loss), ('recon', val_recon), ('kld', val_kld)]:
            history[f'val_{key}'].append(val)

        if (epoch + 1) % 10 == 0:
            print(f"Epoch {epoch+1}/{args.epochs} | "
                  f"Train: {train_loss:.4f} (R:{train_recon:.4f}, K:{train_kld:.4f}) | "
                  f"Val: {val_loss:.4f} (R:{val_recon:.4f}, K:{val_kld:.4f})")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_loss': val_loss,
                'field_mean': dataset.field_mean,
                'field_std': dataset.field_std,
                'cond_mean': dataset.cond_mean,
                'cond_std': dataset.cond_std,
            }, args.checkpoint)
            print(f"  -> Saved best model (val_loss: {val_loss:.4f})")

        early_stopping(val_loss)
        if early_stopping.early_stop:
            print(f"Early stopping at epoch {epoch+1}")
            break

    plot_history(history, args.output_dir)

    print(f"\nTraining complete! Best val loss: {best_val_loss:.4f}")
    print(f"Model saved to {args.checkpoint}")

# =============================================================================
# GENERATION
# =============================================================================

def generate_augmented(args):
    device = get_device()

    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)
    dataset = RDEDataset(args.data, args.csv, normalize=True)

    model = RDECVAEModel(
        in_channels=6,
        spatial_dim=args.spatial_dim,
        hidden_dim=args.hidden_dim,
        latent_dim=args.latent_dim,
        condition_dim=4,
        num_lstm_layers=args.num_lstm_layers,
        dropout=args.dropout
    ).to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    n_anchors = len(dataset)
    n_synthetic_per_anchor = args.num_cases // n_anchors

    synthetic_conditions = []
    synthetic_fields_list = []

    print(f"\nGenerating {args.num_cases} synthetic cases ({n_synthetic_per_anchor} per anchor)...")

    with torch.no_grad():
        for i in range(n_anchors):
            anchor_cond = dataset.conditions[i]

            for j in range(n_synthetic_per_anchor):
                noise = torch.randn_like(torch.from_numpy(anchor_cond)) * 0.1
                synth_cond = torch.from_numpy(anchor_cond) + noise
                synth_cond = synth_cond.to(device)

                synthetic = model.generate(synth_cond, num_timesteps=dataset.n_timesteps, device=device)

                synthetic = synthetic.cpu().numpy()
                synthetic = synthetic * dataset.field_std + dataset.field_mean

                synthetic_fields_list.append(synthetic[0])
                synthetic_conditions.append(synth_cond.cpu().numpy())

    synthetic_fields = np.array(synthetic_fields_list, dtype=np.float32)
    synthetic_conditions = np.array(synthetic_conditions, dtype=np.float32)
    synthetic_conditions = synthetic_conditions * dataset.cond_std + dataset.cond_mean

    output_path = Path(args.output_dir) / 'synthetic_dataset.npz'
    np.savez_compressed(output_path,
                       fields=synthetic_fields,
                       conditions=synthetic_conditions,
                       is_synthetic=np.ones(len(synthetic_fields), dtype=bool))

    print(f"\nSaved {len(synthetic_fields)} synthetic cases to {output_path}")
    print(f"Shape: {synthetic_fields.shape}")

    df_rows = []
    for i, cond in enumerate(synthetic_conditions):
        for t in range(synthetic_fields.shape[1]):
            means = synthetic_fields[i, t].mean(axis=(1, 2))
            df_rows.append({
                'case': f'SYN_{i+1:03d}',
                'time': t,
                'phi': cond[0],
                'p0_pa': cond[1],
                'T0_k': cond[2],
                'cj_speed_ms': cond[3],
                'p_mean': means[0],
                'T_mean': means[1],
                'Ux_mean': means[2],
                'Uy_mean': means[3],
                'H2_mean': means[4],
                'O2_mean': means[5],
                'is_synthetic': True
            })

    df = pd.DataFrame(df_rows)
    csv_path = Path(args.output_dir) / 'synthetic_dataset.csv'
    df.to_csv(csv_path, index=False)
    print(f"Saved tabular data to {csv_path}")

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='RDE CVAE Complete Pipeline')
    parser.add_argument('--mode', type=str, default='train', choices=['train', 'generate'])
    parser.add_argument('--data', type=str, default='spatial_fields.npz')
    parser.add_argument('--csv', type=str, default='RDE_hybrid_dataset_v9.csv')
    parser.add_argument('--checkpoint', type=str, default='best_model.pt')
    parser.add_argument('--output_dir', type=str, default='./output')

    parser.add_argument('--spatial_dim', type=int, default=128)
    parser.add_argument('--hidden_dim', type=int, default=128)
    parser.add_argument('--latent_dim', type=int, default=64)
    parser.add_argument('--num_lstm_layers', type=int, default=2)
    parser.add_argument('--dropout', type=float, default=0.1)

    parser.add_argument('--epochs', type=int, default=500)
    parser.add_argument('--batch_size', type=int, default=2)
    parser.add_argument('--lr', type=float, default=1e-4)
    parser.add_argument('--kld_weight', type=float, default=0.001)
    parser.add_argument('--patience', type=int, default=30)

    parser.add_argument('--num_cases', type=int, default=60)

    args = parser.parse_args()
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    if args.mode == 'train':
        train(args)
    else:
        generate_augmented(args)


if __name__ == '__main__':
    main()