# Dataset and third-party attribution

The experiment uses **Sailesh Dahal's Nepali-English Code-Switched ASR** dataset, published at [saileshbro/nepali-cs-asr](https://huggingface.co/datasets/saileshbro/nepali-cs-asr).

- Exact evaluated revision: `dd00ca41dd38774cd6097c372c16939d7f3746df`, default configuration, test split.
- [Pinned dataset card](https://huggingface.co/datasets/saileshbro/nepali-cs-asr/blob/dd00ca41dd38774cd6097c372c16939d7f3746df/README.md).
- License recorded in that exact card: [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). The pinned card was retrieved again on November 24, 2026; its SHA-256 is `b0f6d62102fbedf85b46142637d5d34c583a094cc3019c5239c4242c74fe280c`.
- Published transcripts/metadata occur in the frozen manifests, saved prediction records, audit files and quoted diagnostics. These references are attributed to the dataset author; this project does not claim to have created the source corpus.
- Changes: the primary references remain unchanged. The diagnostic audit retains 42 references and corrects eight of the selected 50, with separate lexical language tags and CMI. The post-hoc review marks clip-scoped candidate word variants and retains correction history. Those additions do not replace the source dataset or establish independent gold labels.
- The dataset card identifies educational YouTube channels as the original audio sources and asks users to check source terms before further audio redistribution. **This repository distributes no source audio/video or model weights.** Notebook playback outputs are removed from the publication files; private cached audio remains ignored.

Dataset citation:

```bibtex
@dataset{dahal2026nepali,
  author = {Dahal, Sailesh},
  title = {Nepali--English Code-Switched ASR},
  year = {2026},
  publisher = {HuggingFace},
  url = {https://huggingface.co/datasets/saileshbro/nepali-cs-asr},
  note = {v2, channel-disjoint splits; evaluated revision dd00ca41dd38774cd6097c372c16939d7f3746df}
}
```

Local inference uses [SYSTRAN faster-whisper](https://github.com/SYSTRAN/faster-whisper) and converted Whisper Large V2 weights. Hosted outputs were obtained with OpenAI's whisper-1 transcription endpoint. Software/model names identify the evaluated systems and imply no provider endorsement. The report contains the research bibliography and limitations.
