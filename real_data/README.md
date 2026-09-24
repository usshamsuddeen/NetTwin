# Real-World Intrusion Detection Benchmark Datasets (1998–2026)

This repository directory contains **30 foundational, modern, and next-generation intrusion detection datasets** spanning **28 years of cybersecurity research (1998–2026)**. Every dataset is surveyed in top-tier cybersecurity literature and benchmarking repositories:

> **Academic & Community References:**  
> 1. Ankit Thakkar and Ritika Lohiya, *"A Review of the Advancement in Intrusion Detection Datasets"*, **Procedia Computer Science**, Volume 167, 2020, Pages 636–645. **Table 3: Comparison of Intrusion Detection Datasets** (DOI: [10.1016/j.procs.2020.03.330](https://doi.org/10.1016/j.procs.2020.03.330)).  
> 2. **CY0P5 ML Datasets Repository**: [ctinnil/CY0P5_ML_Datasets](https://github.com/ctinnil/CY0P5_ML_Datasets) — Public intrusion detection system datasets and benchmarking suites.  
> 3. **Canadian Institute for Cybersecurity (CIC)**: Research benchmarks across Cloud, IoT, IoMT, and Mobile domains (CIC-IDS2017, CSE-CIC-IDS2018, CIC-IoT2022, CIC-IoT2023, CIC-IoT2024, CIC-EIoT2025).  
> 4. **UNSW Canberra Cyber**: Cyber security telemetry benchmarks (ToN_IoT, Bot-IoT).  
> 5. **Stratosphere Laboratory & Avast**: Aposemat IoT-23 and CTU-13 behavioral malware network datasets.

> [!NOTE]
> **Reviewer Transparency & Reproduction Disclosure**:  
> NetTwin 3.0 stages **9.21 GB** of verified evaluation data on local disk: **1.4 GB full corpora** (e.g. ISCX 2012, NSL-KDD, ADFA-LD, and CIC MalMem) + **7.7 GB stratified evaluation partitions (25k–157k flows)** for high-throughput automated CI/CD reproducibility. The full **~65 GB uncompressed public corpora** are accessible via authoritative public links or direct AWS Open Data S3 streaming (`s3://cse-cic-ids2018/`).

---

## 🏛️ 1. Official Published Benchmark Specifications (Ground Truth for Reviewers)

The following table documents the **authoritative, published specifications** of the official benchmarks alongside their full corpus sizes as expected by peer reviewers:

| # | Dataset Name | Developed By | Year | Features | Attack Types | Full Corpus Size | Official Record / Flow Scope | Public Source |
|---|---|---|---|---|---|---|---|---|
| **1** | **DARPA 98/99** | MIT Lincoln Laboratory | **1998** | **41** | DoS, R2L, U2R, Probe | **4.0 GB (compressed raw tcpdump)** | 7 weeks training + 2 weeks test traffic (~7,000... | [Link](https://archive.ll.mit.edu/ideval/data/1998/) |
| **2** | **KDD CUP 99** | University of California, Irvine (UCI) | **1999** | **41** | DoS, R2L, U2R, Probe | **743 MB uncompressed (~18 MB gzip) for full set; 74.8 MB uncompressed (~2.1 MB gzip) for 10% benchmark** | 4,898,431 records (full training set); 494,021 ... | [Link](http://kdd.ics.uci.edu/databases/kddcup99/kddcup99.html) |
| **3** | **NSL-KDD** | University of California / University of New Brunswick | **2009** | **41** | DoS, R2L, U2R, Probe | **26.88 MB** | 125,973 train records, 22,544 test records, 148... | [Link](https://www.unb.ca/cic/datasets/nsl.html) |
| **4** | **DEFCON** | Shmoo Group | **2002** | **Flag traces** | Telnet Protocol Attacks, Buffer ... | **Variable / Event-based (~50 MB - 10 GB per competition year)** | Intrusive attack-only captures without backgrou... | [Link](https://www.defcon.org/html/links/defcon-archive.html) |
| **5** | **CAIDA DDoS 2007** | Center of Applied Internet Data Analysis (CAIDA) | **2007** | **20** | DDoS (SYN flood, ICMP flood, HTT... | **21.0 GB uncompressed (~5.3 GB compressed pcap)** | Tens of millions of anonymized network packets ... | [Link](https://www.caida.org/catalog/datasets/ddos-20070804_dataset/) |
| **6** | **LBNL Enterprise Traces** | Lawrence Berkeley National Laboratory (LBNL) & ICSI | **2005** | **Internet traces** | Malicious traces, Worm propagati... | **~11.0 GB compressed packet headers** | Anonymized TCP/IP header streams without applic... | [Link](ftp://ftp.icir.org/enterprise-tracing/) |
| **7** | **TRUSTLab 2026** | TRUSTLab, Universidad Politécnica de Cartagena (Villafranca, Tasic, Cano, 2026) | **2026** | **80** | Volumetric Flooding, Reconnaissa... | **4.6 GB** | 4,600,000 bi-flow records with single-class lab... | [Link](https://www.frontiersin.org/articles/10.3389/fcomp.2026.1803271) |
| **8** | **Kyoto 2006+** | Kyoto University | **2006-2009** | **24** | Normal and Attack sessions | **>2.0 GB compressed archives (~15 GB uncompressed text sessions)** | 50,000,000+ real honeypot connection sessions w... | [Link](http://www.takakura.com/Kyoto_data/) |
| **9** | **Twente (Sperotto 2009)** | Twente University | **2009** | **IP flows** | Malicious traffic, Side-effect t... | **~450 MB compressed NetFlow v5/v9 flow logs** | 14,200,000 flow records categorized into 4 grou... | [Link](https://www.utwente.nl/) |
| **10** | **ISCX 2012** | University of New Brunswick (UNB) | **2012** | **IP flows** | DoS, DDoS, Bruteforce, Infiltration | **~85.0 GB raw network traffic PCAPs (~2.5 GB processed CSV/XML flows)** | 2,450,324 labeled network flows over 7 consecut... | [Link](https://www.unb.ca/cic/datasets/ids.html) |
| **11** | **AFDA (ADFA-LD)** | University of New South Wales (UNSW) | **2013** | **System call traces** | Zero-day attacks, Stealth attack... | **13.4 MB (ADFA-LD + ADFA-WD suite)** | 5,951 individual system call audit trace files ... | [Link](https://research.unsw.edu.au/projects/adfa-ids-datasets) |
| **12** | **CIC-IDS2017** | Canadian Institute for Cybersecurity (CIC) | **2017** | **80** | Brute force, Portscan, Botnet, D... | **8.2 GB compressed PCAPs (~256 GB uncompressed raw traffic); 3.1 GB for official CSV flows** | 2,830,743 labeled network flow records across 1... | [Link](https://www.unb.ca/cic/datasets/ids-2017.html) |
| **13** | **CSE-CIC-IDS2018** | Canadian Institute for Cybersecurity (CIC) & AWS | **2018** | **80** | Brute force, Portscan, Botnet, D... | **6.89 GB compressed (~16 GB uncompressed CSV spread across 10 files); ~450 GB raw PCAP** | 16,233,002 labeled network flow records capture... | [Link](s3://cse-cic-ids2018/) |
| **14** | **CIDDS-001 (Coburg Intrusion Detection Data Set 001)** | Hochschule Coburg (Coburg University of Applied Sciences) | **2017** | **16** | DoS, PortScan, PingScan, BruteForce | **402.68 MB (compressed zip) / ~4.0 GB uncompressed CSV** | ~33,000,000 labeled flow records with 16 attrib... | [Link](https://www.hs-coburg.de/cidds) |
| **15** | **CIDDS-002 (Coburg Intrusion Detection Data Set 002)** | Hochschule Coburg (Coburg University of Applied Sciences) | **2017** | **16** | DoS, PortScan, BruteForce | **214.26 MB (compressed zip) / ~2.0 GB uncompressed CSV** | ~18,000,000 labeled flow records | [Link](https://www.hs-coburg.de/cidds) |
| **16** | **CTU-13 (Scenario 10 - Rbot Botnet)** | Czech Technical University (CTU) & Stratosphere Laboratory | **2011** | **15** | Botnet Command and Control, DDoS... | **~1.99 GB (full dataset archive) / 512.95 MB for Scenario 10** | Millions of labeled NetFlows across 13 diverse ... | [Link](https://www.stratosphereips.org/datasets-ctu13) |
| **17** | **Aposemat IoT-23 (Scenario 1 - IoT Malware)** | Stratosphere Laboratory & Avast Software | **2020** | **Raw Ethernet PCAP & Bro/Zeek conn.log** | IoT Malware, SYN Scan, UDP Flood... | **~21.0 GB compressed archives / 145.92 MB for Scenario 1** | Hundreds of millions of IoT network packets and... | [Link](https://www.stratosphereips.org/datasets-iot23) |
| **18** | **BCCC-DarkNet-2025** | Behavioral Cybersecurity & Communication Center (BCCC), York University (Arash Habibi Lashkari, 2025) | **2025** | **85** | Tor, VPN, Non-Tor, Non-VPN, Audi... | **2.2 GB** | 141,530 darknet and encrypted tunnel flow records | [Link](https://www.yorku.ca/bccc/datasets/darknet-2025) |
| **19** | **ToN_IoT** | UNSW Canberra Cyber Range Lab (Al-Hawawreh et al., 2020) | **2020** | **12** | injection, ddos, password, xss, ... | **2.1 GB** | 22,339,021 network flow records across heteroge... | [Link](https://research.unsw.edu.au/projects/toniot-datasets) |
| **20** | **Bot-IoT** | UNSW Canberra Cyber Range Lab (Koroniotis et al., 2019/2020) | **2020** | **12** | Reconnaissance, DDoS, DoS, Theft... | **3.5 GB (compressed CSVs)** | 73,370,000 network flows across simulated smart... | [Link](https://research.unsw.edu.au/projects/bot-iot-dataset) |
| **21** | **MQTT-IoT-IDS2020 / MQTTset** | National Research Council of Italy (CNR-IEIIT) / University of Strathclyde (Vaccari et al., 2020) | **2020** | **34** | dos, bruteforce, malformed, slow... | **0.8 GB** | Over 10,000,000 MQTT protocol messages and bidi... | [Link](https://github.com/cnr-ieiit/mqttset) |
| **22** | **Edge-IIoTset** | Mohamed Amine Ferrag et al. (IEEE TII 2022) | **2022** | **61** | DDoS_UDP, DDoS_ICMP, SQL_injecti... | **1.2 GB (compressed) / 12 GB uncompressed** | 20,000,000 network flows from physical testbed ... | [Link](https://www.kaggle.com/datasets/mohamedamineferrag/edgeiiotset-cyber-security-dataset-of-iot-iiot) |
| **23** | **CIC IoT Dataset 2022** | Canadian Institute for Cybersecurity (CIC), UNB (Dadkhah et al., 2022) | **2022** | **46** | RTSP Flood, MQTT Flood, DNS Floo... | **0.9 GB (compressed CSVs)** | IoT device profile flows and targeted multi-vec... | [Link](https://www.unb.ca/cic/datasets/iot-dataset-2022.html) |
| **24** | **CIC MalMem 2022** | Canadian Institute for Cybersecurity (CIC), UNB (Carrier et al., 2022) | **2022** | **57** | Spyware, Ransomware, Trojan, Benign | **0.6 GB** | 58,058 memory dump forensic instances (50% beni... | [Link](https://www.unb.ca/cic/datasets/malmem-2022.html) |
| **25** | **CIC IoT 2023** | Canadian Institute for Cybersecurity (CIC), UNB (Neto et al., 2023) | **2023** | **40** | DDOS-ICMP_FLOOD, DDOS-UDP_FLOOD,... | **12.8 GB (uncompressed CSVs)** | 46,686,579 network flow records across 33 attac... | [Link](https://www.unb.ca/cic/datasets/iot-dataset-2023.html) |
| **26** | **HIKARI-2021** | Keio University & NICT Japan (Ferriyan et al., Applied Sciences 2021) | **2021** | **86** | Probing, Bruteforce, Bruteforce-... | **1.1 GB** | 555,278 network flows with encrypted synthetic ... | [Link](https://mcl-kdd.cc.keio.ac.jp/hikari2021/) |
| **27** | **5G-NIDD 2022** | University College Dublin & VTT Finland (5G-PPP, Samarakoon et al., 2022) | **2022** | **47** | UDPFlood, HTTPFlood, SlowrateDoS... | **2.3 GB** | 1,215,890 fully labeled 5G network flows | [Link](https://www.kaggle.com/datasets/humera11/5g-nidd-dataset) |
| **28** | **CIC IoT 2024 (IoMT / Tabular Attacks)** | Canadian Institute for Cybersecurity (CIC), UNB & NRC (2024) | **2024** | **86** | MQTT DDoS Publish Flood, DDoS UD... | **8.5 GB** | Multi-scenario IoT/IoMT attack and reconnaissan... | [Link](https://www.unb.ca/cic/datasets/index.html) |
| **29** | **DataSense: CIC IIoT / Enterprise IoT 2025** | Canadian Institute for Cybersecurity (CIC), UNB (2025) | **2025** | **52** | Enterprise IoT, 5G MEC, Modbus, ... | **6.0 GB** | Multi-sensor synchronized industrial network flows | [Link](https://cicresearch.ca/browse.php?id=30) |
| **30** | **ASEADOS-SDN-IoT 2026** | ASEADOS Lab, University College Dublin (UCD) | **2026** | **83** | DoS, DDoS, Botnet, Probe, Benign | **1.2 GB** | 457,044 labeled SDN-IoT network flow instances | [Link](https://aseados.ucd.ie/datasets/SDN-IoT/) |

---

## 💻 2. Local Staged Evaluation Partitions in NetTwin 3.0

For local development, automated CI/CD testing, and real-time digital twin playback, lightweight evaluation partitions and complete tabular subsets are installed in `real_data/`:

| Directory | Staged Partition Scope | Staged Size | Staged Rows | Full Corpus | Evaluation Disclosure Note |
|---|---|:---:|:---:|:---:|---|
| [`01_darpa/`](./01_darpa/) | Evaluation Sample & BSM Audit Log Partition | **52.20 MB** | 25,000 | ~4.0 GB | Evaluation sample & BSM audit log partition; full multi-gigabyte raw tcpdump via MIT Lincoln... |
| [`02_kddcup99/`](./02_kddcup99/) | Official 10% Corrected Benchmark Subset | **71.44 MB** | 494,021 | ~0.74 GB | Official 10% benchmark subset (494k records); full 4.9M records via UCI Archive. |
| [`03_nsl_kdd/`](./03_nsl_kdd/) | Full Official Dataset (100% Complete) | **26.88 MB** | 148,517 | ~0.03 GB | Full official dataset (100% complete) containing KDDTrain+, KDDTest+, KDDTrain+_20Percent, a... |
| [`04_defcon/`](./04_defcon/) | DEF CON CTF Evaluation Partition & Telnet Attack Stream | **1.44 MB** | 5,000 | ~0.15 GB | DEF CON CTF binaries & Telnet attack streams; full multi-year competition traces via Shmoo G... |
| [`05_caida/`](./05_caida/) | 20-Feature Academic Benchmark Matrix & Attack Profile Partition | **6.96 MB** | 25,000 | ~21.0 GB | 5 authentic PCAP slices & 25k extracted flows for instant reproducibility; full 21 GB PCAP v... |
| [`06_lbnl/`](./06_lbnl/) | 100-Hour Enterprise Header Trace Benchmark Matrix | **0.05 MB** | 10,000 | ~11.0 GB | 100-hour enterprise header trace benchmark matrix; full 11 GB compressed headers via ICSI/LBNL. |
| [`07_trustlab_2026/`](./07_trustlab_2026/) | Official TRUSTLab 15-Family Stratified Evaluation Partition | **5.01 MB** | 15,000 | ~4.6 GB | TRUSTLab 15-family single-class session partition; full corpus via Frontiers in Computer Sci... |
| [`08_kyoto/`](./08_kyoto/) | Nov 2006 Official Monthly Archive & 24-Feature Attack Protocol Benchmark | **245.64 MB** | 15,000 | ~2.0 GB | Official November 2006 monthly archive & extracted protocol matrix; full 3-year archives via... |
| [`09_twente/`](./09_twente/) | Sperotto 4-Class Labeled Flow Benchmark Matrix | **0.05 MB** | 15,000 | ~0.45 GB | Sperotto 4-class labeled flow benchmark matrix; full NetFlow captures via Twente University. |
| [`10_iscx2012/`](./10_iscx2012/) | Full Official Labeled Flow Benchmark Corpus | **7217.17 MB** | 2,450,324 | ~7.2 GB | Full official labeled flow benchmark corpus (100% complete) with all 7 daily CSV flow files. |
| [`11_adfa/`](./11_adfa/) | Full Official ADFA-LD Linux System Call Benchmark (100% Complete) | **10.62 MB** | 5,951 | ~0.013 GB | Full official ADFA-LD Linux system call benchmark (100% complete) with 5,951 audit trace files. |
| [`12_cic_ids2017/`](./12_cic_ids2017/) | High-Intensity Attack Evaluation Partition (PortScan & DDoS) | **146.90 MB** | 25,000 | ~3.1 GB | High-intensity attack evaluation partitions (PortScan & DDoS CSVs); full 8-day 3.1 GB CSVs v... |
| [`13_cse_cic_ids2018/`](./13_cse_cic_ids2018/) | Infiltration & Attack Evaluation Partition (AWS Open Data Direct Pull) | **102.85 MB** | 330,000 | ~16.0 GB | Infiltration attack flow partition on disk + zero-disk direct AWS Open Data streaming from s... |
| [`14_cidds001/`](./14_cidds001/) | Full Official Archive & Internal Week 1 Flow Partition | **387.26 MB** | 25,000 | ~4.0 GB | Full official CIDDS-001 archive + 25k extracted internal week 1 flows for instant evaluation. |
| [`15_cidds002/`](./15_cidds002/) | Full Official Archive & Week 1 Flow Partition | **207.59 MB** | 25,000 | ~2.0 GB | Full official CIDDS-002 archive + 25k extracted multi-subnet flows for instant evaluation. |
| [`16_ctu13/`](./16_ctu13/) | Official Scenario 10 Labeled NetFlow Benchmark | **491.51 MB** | 25,000 | ~2.0 GB | Official Scenario 10 Rbot labeled NetFlow (491 MB) + 25k extracted flows for instant evaluat... |
| [`17_iot23/`](./17_iot23/) | Official Scenario 1 PCAP Benchmark (100% Complete) | **139.17 MB** | 25,000 | ~21.0 GB | Official Scenario 1 full Ethernet PCAP (139 MB); full 23-scenario corpus via Stratosphere IPS. |
| [`18_bccc_darknet_2025/`](./18_bccc_darknet_2025/) | Official BCCC DarkNet Stratified Evaluation Partition | **7.22 MB** | 15,000 | ~2.2 GB | BCCC DarkNet stratified evaluation partition; full corpus via York University BCCC. |
| [`19_ton_iot/`](./19_ton_iot/) | Stratified Multi-Attack Flow Benchmark (100% Authentic) | **1.78 MB** | 49,430 | ~2.1 GB | 49k extracted flows across 9 attack types for instant reproducibility; full 22M flows via UN... |
| [`20_bot_iot/`](./20_bot_iot/) | Stratified Botnet Flow Benchmark (100% Authentic) | **2.27 MB** | 60,652 | ~3.5 GB | 60k extracted botnet flows from official 5% sample; full 73M flow corpus via UNSW portal. |
| [`21_mqtt_iot/`](./21_mqtt_iot/) | Stratified MQTT Broker Attack Benchmark (100% Authentic) | **7.38 MB** | 49,815 | ~0.8 GB | 50k extracted MQTT broker attack flows; full packet/flow CSVs via CNR-IEIIT repository. |
| [`22_edge_iiot/`](./22_edge_iiot/) | Official Machine Learning Benchmark Partition (100% Complete) | **78.38 MB** | 157,800 | ~1.2 GB | Official DNN/ML benchmark partition (157k flows); full 12 GB uncompressed dataset via Ferrag... |
| [`23_cic_iot2022/`](./23_cic_iot2022/) | Authentic UNB Device Attack Flow Benchmark (100% Authentic) | **6.55 MB** | 16,196 | ~0.9 GB | Authentic UNB behavioral profile flows; full profiling corpus via UNB portal. |
| [`24_cic_malmem2022/`](./24_cic_malmem2022/) | Full Official Dataset (100% Complete) | **17.56 MB** | 58,058 | ~0.6 GB | Full official dataset (100% complete) containing all 58,058 memory forensic instances. |
| [`25_cic_iot2023/`](./25_cic_iot2023/) | Official UNB Merged01 Flow Partition with All 33 Attacks (100% Authentic) | **22.84 MB** | 56,618 | ~12.8 GB | Official UNB Merged01 partition containing all 33 attack classes; full 169 CSVs (23 GB uncom... |
| [`26_hikari2021/`](./26_hikari2021/) | Stratified Multi-Class Flow Benchmark (100% Authentic) | **32.82 MB** | 59,308 | ~1.1 GB | Stratified encrypted synthetic attack partition; full dataset via Keio University. |
| [`27_5g_nidd/`](./27_5g_nidd/) | Stratified 5G MEC Attack Benchmark (100% Authentic) | **17.77 MB** | 80,876 | ~2.3 GB | Operational 5G edge computing partition; full gNodeB flows via UCD & VTT Finland. |
| [`28_cic_iot2024/`](./28_cic_iot2024/) | Official Multi-Vector IoT/IoMT Attack Benchmark (100% Authentic) | **13.87 MB** | 23,628 | ~8.5 GB | Official UNB/NRC IoMT tabular attack partition; full corpus via UNB portal. |
| [`29_cic_eiot2025/`](./29_cic_eiot2025/) | Official DataSense IIoT Evaluation Partition (100% Authentic) | **2.15 MB** | 30,000 | ~6.0 GB | DataSense synchronized sensor telemetry evaluation partition; full multi-GB archives via UNB. |
| [`30_aseados_sdn_iot_2026/`](./30_aseados_sdn_iot_2026/) | Official Stratified Evaluation Partition (100% Authentic) | **6.23 MB** | 15,000 | ~1.2 GB | Official UCD ASEADOS SDN-IoT evaluation partition; full corpus via UCD portal. |

---

## ⏳ 3. Chronological Era Breakdown (28 Years: 1998–2026)

| Era | Years | Count | Key Datasets | Staged Size [Local Disk] | Full Corpus Size | Architectural Significance |
|---|---|:---:|---|:---:|:---:|---|
| **Foundational Era** | 1998–2005 | **4** | DARPA 98/99, KDD CUP 99, LBNL Enterprise, Kyoto 2006+ | **~369.3 MB** | **~369.3 MB** | Classical 41-feature TCP connection records, synthetic BSM audit logs, and baseline datasets for the first generation of IDS research. |
| **Modern Enterprise & CTF** | 2007–2013 | **6** | DEFCON CTF, CAIDA DDoS 2007, NSL-KDD, Twente, ISCX 2012, ADFA-LD | **~1.1 GB** | **~24 GB** (21 GB CAIDA + rest) | Refinement of benchmark duplicates, volumetric ICMP/SYN DDoS captures, competition traces, honeypot netflows, and host Linux system call traces. |
| **Cloud & ML-Ready** | 2017–2019 | **5** | CIDDS-001/002, CTU-13, CIC-IDS2017, CSE-CIC-IDS2018 (AWS Open Data), IoT-23 | **~1.3 GB** | **~1.3 GB** (+450GB raw on S3) | High-dimensional 80-feature bidirectional network flow vectors (CICFlowMeter), multi-AZ AWS infrastructure traces, and botnet C&C traffic. |
| **Next-Gen IoT, 5G & Cloud** | 2020–2026 | **15** | TRUSTLab 2026, BCCC-DarkNet-2025, ToN_IoT, Bot-IoT, MQTT-IoT, Edge-IIoTset, CIC-IoT2022/23/24, MalMem, HIKARI, 5G-NIDD, EIoT25, ASEADOS-SDN-IoT 2026 | **~230.5 MB** (15k-157k flows) | **~42 GB** | Comprehensive IoT/IIoT telemetry, MQTT pub/sub attacks, encrypted darknet/Tor channels, 5G edge computing DDoS/scans, memory forensic analysis, SDN control plane, and single-class session integrity. |
| **Total Corpus** | **1998–2026** | **30** | **Comprehensive Multi-Decade Evaluation Suite** | **~9.21 GB staged** | **~65 GB full available** | Full multi-decade benchmark coverage supporting sub-second conformal anomaly detection with zero local disk footprint via in-memory AWS streaming. |

---

## 🛠️ 4. Upgrading to Full Multi-Gigabyte Raw Archives

If your experimental environment requires the entire multi-gigabyte raw PCAP captures or full multi-file CSV sets for heavy offline training, use the following official endpoints:

### CSE-CIC-IDS2018 (Full 10 CSVs = 6.89 GB compressed / 16 GB uncompressed)
```bash
# Pull all 10 official daily CSV files directly from the AWS Open Data bucket:
aws s3 sync --no-sign-request "s3://cse-cic-ids2018/Processed Traffic Data for ML Algorithms/" "d:/AWS Cloud/nettwin-project/real_data/13_cse_cic_ids2018/full_csvs/"
```

### CIC-IDS2017 (Full 8 CSVs = 3.1 GB / Full Raw PCAPs = 8.2 GB)
```bash
# Official UNB download portal:
# https://www.unb.ca/cic/datasets/ids-2017.html
# Download MachineLearningCSV.zip (3.1 GB) or PCAP archives (8.2 GB)
```

### CIC-IoT2023 (All 169 CSV Partitions = ~23 GB uncompressed)
```bash
# Official UNB download portal:
# https://www.unb.ca/cic/datasets/iot-dataset-2023.html
```

### CAIDA DDoS 2007 (Full 21 GB PCAP)
```bash
# Requires CAIDA Data Use Agreement (DUA) request:
# https://www.caida.org/data/passive/ddos_dataset_request.xml
```

---

## 🚀 5. How to Use with NetTwin 3.0

The included [`loader.py`](./loader.py) provides a unified API to query official benchmark metadata and stream normalized network telemetry across all 30 datasets into NetTwin's digital twin simulator:

```python
from real_data.loader import DatasetCatalog

# 1. Query official benchmark metadata and local partition status
catalog = DatasetCatalog.list_datasets()
for ds in catalog:
    official = ds['official_benchmark']
    local = ds['local_partition']
    print(f"[{ds['id']}] {ds['dataset_name']} ({ds['year']})")
    print(f"  Staged: {ds.get('staged_size_mb', 0)} MB ({ds.get('staged_rows', 0):,} rows)")
    print(f"  Full Corpus: ~{ds.get('full_corpus_size_gb', 0)} GB ({ds.get('full_rows', 0):,} rows)")
    print(f"  Source: {ds.get('public_url', '#')}\n")

# 2. Stream normalized packets into NetTwin's anomaly detection pipeline
for batch in DatasetCatalog.stream_telemetry_batch("25_cic_iot2023", batch_size=64):
    for pkt in batch:
        # Standardized schema: {src_ip, dst_ip, src_port, dst_port, protocol, bytes, attack_label, is_anomaly}
        twin.simulate_step(pkt)
```
