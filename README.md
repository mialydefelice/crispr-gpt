<div align="center">

# CRISPR-GPT for agentic automation of gene-editing experiments

<div>
🧬 Multi-Agent System for Automated CRISPR Experiment Design and Analysis 🔬
</div>
</div>

<br>
<div align="center">
<!-- Buttons -->
<a href="https://www.nature.com/articles/s41551-025-01463-z" style="text-decoration:none;">
  <img src="https://img.shields.io/badge/Paper-Nature%20BME-red?style=for-the-badge&logo=readthedocs&logoColor=white" 
       style="height:30px; margin:10px;">
<br>

<a href="https://genomics.stanford.edu" style="text-decoration:none;">
  <img src="https://img.shields.io/badge/Website-genomics.stanford.edu-blue?style=for-the-badge&logo=google-chrome&logoColor=white" 
       style="height:30px; margin:10px;">
<br>
</a>
<br>
<p style="font-size:20px; font-weight:bold; margin-top:20px;">
  Please sign-up for beta access to CRISPR-GPT:
</p>
<a href="https://www.surveymonkey.com/r/G9GCMJV" style="text-decoration:none;">
  <img src="https://img.shields.io/badge/Early%20Access-Sign%20Up-green?style=for-the-badge&logo=check-circle&logoColor=white" 
       style="height:30px; margin:10px;">
</a>
</div>

</div>

## Overview

<p align="center">
<img width="600" alt="CRISPR-GPT Overview" src="assets/fig1.png">
</p>

CRISPR-GPT is an innovative Large Language Model (LLM) agent designed to automate and streamline the process of designing gene-editing experiments. By leveraging the power of advanced language models, CRISPR-GPT assists researchers in planning, executing, and analyzing CRISPR-based gene editing tasks with unprecedented efficiency and accuracy.

CRISPR-GPT supports four primary gene-editing modalities: **knockout**, **base-editing**, **prime-editing**, and **epigenetic editing**. The system automates 22 individual tasks including CRISPR/Cas system selection, sgRNA design, off-target prediction, delivery method optimization, and experimental validation protocols. Users can interact with CRISPR-GPT through three distinct modes: (1) **Meta mode** for step-by-step guidance on pre-defined gene-editing workflows, (2) **Auto mode** for customized guidance on free-style user requests, and (3) **QA mode** for real-time answers to ad hoc questions. These modes accommodate different user expertise levels and experimental requirements, from novice researchers seeking structured guidance to experienced scientists needing flexible, custom workflows or quick troubleshooting support.

**Related Work**: This project builds upon our [Genome-Bench](https://github.com/mingyin0312/RL4GenomeBench) research, which developed RL fine-tuning methods to inject expert knowledge from 10+ years of genomics discussions into language models.

## Architecture

<img width="830" alt="CRISPR-GPT Architecture" src="assets/fig2.png">

The backbone of CRISPR-GPT involves multi-agent collaboration between four core components:

1. **LLM Planner Agent**: Configures tasks and performs automatic task decomposition and planning based on user requests
2. **Task Executor Agent**: Implements the chain of state machines from the Planner Agent and manages workflow execution
3. **LLM User-Proxy Agent**: Interfaces with the Task Executor on behalf of users, enabling monitoring and corrections
4. **Tool Providers**: Support diverse external tools and connect to search engines or databases via API calls

## Getting Started

### Release Information

Due to safety concerns regarding AI applications in biological research, the complete CRISPR-GPT codebase (including full data, code, and prompts) will not be publicly released until the development of comprehensive US regulations governing artificial intelligence and its scientific applications.

While the full code is not freely available, **it has undergone rigorous peer review** as part of our Nature Biomedical Engineering publication process.

### Light Version (Developer Preview)

We are releasing a **light version** of CRISPR-GPT on GitHub that includes:

- ✅ Core infrastructure and framework
- ✅ Basic chat interface
- ✅ Limited task/functionality support

### Installation (Light Version)

```bash
# Download Conda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

#Install Conda

# Clone the repository
git clone https://github.com/cong-lab/crispr-gpt-pub.git
cd crispr-gpt-pub

- Accept the license
- Install to default (~/miniconda3)
- Say yes to `conda init`

# Reload Shell
source ~/.bashrc

# Verify Install
conda --version

# Create conda environment
conda create -n crispr-gpt-new python=3.11 -y
conda activate crispr-gpt-new

# Install dependencies
pip install -r requirements.txt

# Set up OpenAI API key
echo "OPENAI_KEY=your_openai_api_key_here" > .env # This is for CRISPRGPT
echo "OPENAI_API_KEY=your_openai_api_key_here" > .env # This is for Biomni

# Run the application
python main.py
```

## Citation

```bibtex
@article{qu2025crisprGPT,
  title={CRISPR-GPT for agentic automation of gene-editing experiments},
  author={Qu, Yuanhao and Huang, Kaixuan and Yin, Ming and others},
  journal={Nature Biomedical Engineering},
  year={2025},
  doi={10.1038/s41551-025-01463-z},
  url={https://doi.org/10.1038/s41551-025-01463-z}
}
```

## Contact

For questions, suggestions, or collaborations, please contact:

**CRISPR-GPT Team**:
- Yuanhao Qu: [yhqu@stanford.edu](mailto:yhqu@stanford.edu)  
- Kaixuan Huang: [kaixuanh@princeton.edu](mailto:kaixuanh@princeton.edu)
- Mengdi Wang: [mengdiw@princeton.edu](mailto:mengdiw@princeton.edu)
- Le Cong: [congle@stanford.edu](mailto:congle@stanford.edu)

---
