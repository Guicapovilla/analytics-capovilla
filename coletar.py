"""Ponto de entrada da coleta (GitHub Actions / local) — delega à pipeline no pacote."""

from youtube_analytics.collector.pipeline import main

if __name__ == "__main__":
    main()
