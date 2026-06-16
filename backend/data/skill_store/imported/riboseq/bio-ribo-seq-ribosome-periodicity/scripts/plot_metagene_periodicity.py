#!/usr/bin/env python3
"""Plot metagene profile around start codon with FFT periodicity spectrum."""
import argparse
import numpy as np
import matplotlib.pyplot as plt
from scipy.fft import fft


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--npz", required=True, help="NPZ file with 'profile' array")
    parser.add_argument("--upstream", type=int, default=50)
    parser.add_argument("--out", default="metagene_start.pdf")
    args = parser.parse_args()

    data = np.load(args.npz)
    metagene_data = data["profile"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    positions = np.arange(-args.upstream, len(metagene_data) - args.upstream)

    for frame in range(3):
        frame_positions = positions[positions % 3 == frame]
        counts = metagene_data[positions % 3 == frame]
        axes[0].bar(frame_positions, counts, alpha=0.7, label=f"Frame {frame}")

    axes[0].set_xlabel("Position relative to start codon")
    axes[0].set_ylabel("Normalized counts")
    axes[0].legend()
    axes[0].axvline(0, color="red", linestyle="--")

    fft_result = np.abs(fft(metagene_data))
    freq = np.fft.fftfreq(len(metagene_data))
    valid = freq > 0
    axes[1].plot(1 / freq[valid], fft_result[valid])
    axes[1].set_xlabel("Period (nt)")
    axes[1].set_ylabel("Power")
    axes[1].axvline(3, color="red", linestyle="--")

    plt.tight_layout()
    plt.savefig(args.out)
    plt.close()


if __name__ == "__main__":
    main()
