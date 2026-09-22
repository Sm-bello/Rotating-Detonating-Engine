
"""
RDE CVAE Validation Script v1.0
Quick sanity check: load model, run one forward pass, visualize reconstruction.

Usage:
    python validate_model.py --data spatial_fields.npz --checkpoint best_model.pt
"""

import torch
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import argparse

from rde_cvae_model import RDECVAEModel
from train_rde_cvae import RDEDataset


def visualize_reconstruction(original, reconstructed, case_id, timestep, output_dir):
    """Plot original vs reconstructed fields."""
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))

    channel_names = ['Pressure (p)', 'Temperature (T)', 'Ux', 'Uy', 'H2', 'O2']

    for i, (ax_orig, ax_recon) in enumerate(zip(axes[0], axes[1])):
        if i >= len(channel_names):
            break

        # Original
        im1 = ax_orig.imshow(original[i], cmap='viridis', aspect='auto')
        ax_orig.set_title(f'Original: {channel_names[i]}')
        ax_orig.set_xlabel('X')
        ax_orig.set_ylabel('Y')
        plt.colorbar(im1, ax=ax_orig, fraction=0.046)

        # Reconstructed
        im2 = ax_recon.imshow(reconstructed[i], cmap='viridis', aspect='auto')
        ax_recon.set_title(f'Reconstructed: {channel_names[i]}')
        ax_recon.set_xlabel('X')
        ax_recon.set_ylabel('Y')
        plt.colorbar(im2, ax=ax_recon, fraction=0.046)

    plt.suptitle(f'Case {case_id}, Timestep {timestep}')
    plt.tight_layout()

    save_path = Path(output_dir) / f'recon_case{case_id}_t{timestep}.png'
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"Saved visualization to {save_path}")


def compute_error_metrics(original, reconstructed):
    """Compute MSE, MAE, PSNR per channel."""
    metrics = {}

    for i, name in enumerate(['p', 'T', 'Ux', 'Uy', 'H2', 'O2']):
        orig = original[i]
        recon = reconstructed[i]

        mse = np.mean((orig - recon) ** 2)
        mae = np.mean(np.abs(orig - recon))

        # PSNR
        max_val = np.max(orig)
        if max_val > 0:
            psnr = 20 * np.log10(max_val / np.sqrt(mse))
        else:
            psnr = 0

        metrics[name] = {'MSE': mse, 'MAE': mae, 'PSNR': psnr}

    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=str, default='spatial_fields.npz')
    parser.add_argument('--csv', type=str, default='RDE_hybrid_dataset_v9.csv')
    parser.add_argument('--checkpoint', type=str, default='best_model.pt')
    parser.add_argument('--output_dir', type=str, default='./validation')
    parser.add_argument('--case_idx', type=int, default=0, help='Which case to validate (0-11)')
    parser.add_argument('--timestep', type=int, default=10, help='Which timestep to visualize')
    args = parser.parse_args()

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    print(f"Loading dataset...")
    dataset = RDEDataset(args.data, args.csv, normalize=True)

    print(f"Loading model from {args.checkpoint}...")
    checkpoint = torch.load(args.checkpoint, map_location=device)

    model = RDECVAEModel().to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    # Get one case
    sample = dataset[args.case_idx]
    fields = sample['fields'].unsqueeze(0).to(device)  # (1, T, C, H, W)
    condition = sample['condition'].unsqueeze(0).to(device)  # (1, 4)

    print(f"Validating Case {args.case_idx}, shape: {fields.shape}")

    # Forward pass
    with torch.no_grad():
        recon, mu, logvar = model(fields, condition)

    # Denormalize
    fields_np = fields.cpu().numpy()[0]  # (T, C, H, W)
    recon_np = recon.cpu().numpy()[0]    # (T, C, H, W)

    fields_np = fields_np * dataset.field_std + dataset.field_mean
    recon_np = recon_np * dataset.field_std + dataset.field_mean

    # Compute metrics for all timesteps
    all_mse = []
    for t in range(fields_np.shape[0]):
        mse = np.mean((fields_np[t] - recon_np[t]) ** 2)
        all_mse.append(mse)

    print(f"\nTemporal MSE: mean={np.mean(all_mse):.4f}, std={np.std(all_mse):.4f}")
    print(f"Best timestep: {np.argmin(all_mse)} (MSE={np.min(all_mse):.4f})")
    print(f"Worst timestep: {np.argmax(all_mse)} (MSE={np.max(all_mse):.4f})")

    # Visualize specific timestep
    t = min(args.timestep, fields_np.shape[0] - 1)
    visualize_reconstruction(
        fields_np[t], recon_np[t], 
        args.case_idx, t, args.output_dir
    )

    # Compute detailed metrics
    metrics = compute_error_metrics(fields_np[t], recon_np[t])
    print(f"\nChannel-wise metrics at t={t}:")
    for ch, vals in metrics.items():
        print(f"  {ch}: MSE={vals['MSE']:.4f}, MAE={vals['MAE']:.4f}, PSNR={vals['PSNR']:.2f} dB")

    # Test generation
    print(f"\nTesting generation...")
    with torch.no_grad():
        synthetic = model.generate(condition[0], num_timesteps=20, device=device)

    synth_np = synthetic.cpu().numpy()[0]  # (T, C, H, W)
    synth_np = synth_np * dataset.field_std + dataset.field_mean

    print(f"Synthetic fields shape: {synth_np.shape}")
    print(f"Synthetic p range: [{synth_np[:,0].min():.2e}, {synth_np[:,0].max():.2e}]")
    print(f"Synthetic T range: [{synth_np[:,1].min():.2f}, {synth_np[:,1].max():.2f}]")

    print(f"\nValidation complete. Check {args.output_dir}/ for visualizations.")


if __name__ == '__main__':
    main()
