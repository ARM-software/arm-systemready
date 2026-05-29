# SystemReady Band ACS Automation Flow

## Overview

This document explains the automation flow of the **Arm SystemReady Band ACS** image.

The SystemReady Band ACS image is a bootable validation environment used to run firmware, UEFI, Linux, architecture, and compliance test suites on Arm SystemReady platforms.

The automation flow covers:

- Image validations
- SystemReady Band ACS Automation Flow
- GRUB Boot Menu Options
- Configuration Files
- Result Collection

---

## What the SR Image Validates

| Validation Area | Tools / Test Suites |
|---|---|
| Firmware compliance | SCT, SCRT, FWTS |
| Base system architecture | BSA |
| Server architecture | SBSA |
| Secure Boot compliance | BBSR |
| Manageability checks | SBMR |
| Linux-side validation | Linux scripts and test tools |
| Result reporting | ACS log parser and waiver flow |

---

## SystemReady Band ACS Automation Flow

This section explains the end-to-end automation flow for the SystemReady Band ACS image.

The flow is divided into two parts:

1. **Build Automation Flow** — how the ACS image is prepared and generated.
2. **Run Automation Flow** — what happens when the ACS image boots on the platform.

---
### SR Build Automation Flow

Commands executed from **arm-systemready/SystemReady-band/**:

```text
./build-scripts/get_source.sh
./build-scripts/build-systemready-band-live-image.sh
```

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Arial",
    "fontSize": "14px",
    "primaryBorderColor": "#0f172a",
    "lineColor": "#2563eb",
    "tertiaryColor": "#ffffff"
  }
}}%%

flowchart TD

    linkStyle default stroke:#2563eb,stroke-width:4px;

    Start((Start)) --> B["Run get_source.sh"]
    B --> C["Fetches ACS and dependent sources"]
    C --> D["Prepares common configs and scripts"]
    D --> E["Applies required patches"]

    E --> F["Run build-systemready-band-live-image.sh"]

    F --> G1["Builds UEFI components"]
    F --> G2["Builds Linux kernel"]
    F --> G3["Builds Buildroot ramdisk"]
    F --> G4["Builds ACS test binaries"]
    F --> G5["Builds parser/helper tools"]

    G1 --> H["Packages SR ACS image"]
    G2 --> H
    G3 --> H
    G4 --> H
    G5 --> H

    H --> I["Adds EFI boot files"]
    I --> J["Adds ACS test content"]
    J --> K["Adds Linux Image and ramdisk"]
    K --> L["Adds config and result directories"]
    L --> M["Generates compressed SR ACS image"]
    M --> End((End))

    classDef startEnd fill:#ffffff,stroke:#0f172a,stroke-width:3px,color:#0f172a;
    classDef manualRun fill:#fef3c7,stroke:#d97706,stroke-width:3px,color:#0f172a;
    classDef source fill:#dbeafe,stroke:#1d4ed8,stroke-width:3px,color:#0f172a;
    classDef build fill:#ffedd5,stroke:#ea580c,stroke-width:3px,color:#0f172a;
    classDef package fill:#dcfce7,stroke:#16a34a,stroke-width:3px,color:#0f172a;
    classDef output fill:#ede9fe,stroke:#7c3aed,stroke-width:3px,color:#0f172a;

    class Start,End startEnd;
    class B,F manualRun;
    class C,D,E source;
    class G1,G2,G3,G4,G5 build;
    class H,I,J,K,L package;
    class M output;
```
---
## SR Runtime Flowcharts
- These diagrams show the high-level runtime automation flow.
- **Reboot handling:** Some test suites intentionally reset the platform after saving results. After reset, the platform returns to **GRUB** and resumes from the next pending stage. Completed suites are skipped using result logs or state.
---
### 1. Runtime Entry Flow

> By default, **SystemReady band ACS (Automation)** is selected and the full automation flow is executed.  
> Click a boot option box to jump to the corresponding flow section in GitHub.

```mermaid
%%{init: {
  "theme": "base",
  "flowchart": {
    "curve": "linear",
    "nodeSpacing": 35,
    "rankSpacing": 45
  },
  "themeVariables": {
    "fontFamily": "Arial",
    "fontSize": "14px",
    "primaryBorderColor": "#0f172a",
    "lineColor": "#2563eb",
    "tertiaryColor": "#ffffff"
  }
}}%%

flowchart LR

    linkStyle default stroke:#2563eb,stroke-width:4px;

    A["GRUB<br/>Menu"] --> B{"Boot<br/>option"}

    B --> C["SystemReady<br/>band ACS<br/><b>Automation</b>"]
    B --> D["Linux<br/>Boot"]
    B --> E["BBSR<br/>Compliance<br/><b>Automation</b>"]

    click C "https://github.com/ARM-software/arm-systemready/blob/main/docs/systemready_band_flow.md#2-systemready-band-acs-automation-flow" "Go to SystemReady band ACS Automation Flow"
    click D "https://github.com/ARM-software/arm-systemready/blob/main/docs/systemready_band_flow.md#3-linux-automation-flow" "Go to Linux Automation Flow"
    click E "https://github.com/ARM-software/arm-systemready/blob/main/docs/systemready_band_flow.md#4-bbsr-automation-flow" "Go to BBSR Automation Flow"

    classDef grub fill:#dbeafe,stroke:#1d4ed8,stroke-width:3px,color:#0f172a;
    classDef decision fill:#ffffff,stroke:#2563eb,stroke-width:3px,color:#0f172a;
    classDef linux fill:#dcfce7,stroke:#16a34a,stroke-width:3px,color:#0f172a;
    classDef uefi fill:#ffedd5,stroke:#ea580c,stroke-width:3px,color:#0f172a;
    classDef bbsr fill:#fef3c7,stroke:#d97706,stroke-width:3px,color:#0f172a;

    class A grub;
    class B decision;
    class C uefi;
    class D linux;
    class E bbsr;
```

---

### 2. SystemReady band ACS Automation Flow

> This flow is executed when **SystemReady band ACS (Automation)** is selected from GRUB.

##### UEFI ACS Flow

```mermaid
%%{init: {
  "theme": "base",
  "flowchart": {
    "curve": "linear",
    "nodeSpacing": 25,
    "rankSpacing": 35
  },
  "themeVariables": {
    "fontFamily": "Arial",
    "fontSize": "14px",
    "primaryBorderColor": "#0f172a",
    "lineColor": "#2563eb",
    "tertiaryColor": "#ffffff"
  }
}}%%

flowchart LR

    linkStyle default stroke:#2563eb,stroke-width:4px;

    A["• SCT<br/>• SCRT"]
    A --> B["• Capsule<br/>  info dump<br/>• UEFI<br/>  debug dump"]

    B --> C["BSA<br/>UEFI"]
    C --> R1["Reset"]

    R1 -->|"SBSA enabled"| D["SBSA<br/>UEFI"]
    R1 -->|"SBSA not enabled"| E["Go to<br/>ACS Linux"]

    D --> R2["Reset"]
    R2 --> E

    classDef uefi fill:#ffedd5,stroke:#ea580c,stroke-width:3px,color:#0f172a;
    classDef reboot fill:#fee2e2,stroke:#dc2626,stroke-width:3px,color:#0f172a;
    classDef linux fill:#dcfce7,stroke:#16a34a,stroke-width:3px,color:#0f172a;

    class A,B,C,D uefi;
    class R1,R2 reboot;
    class E linux;
```

<div align="center">

**➡️ Continues with ACS Linux flow**

</div>

##### Linux ACS Flow

```mermaid
%%{init: {
  "theme": "base",
  "flowchart": {
    "curve": "linear",
    "nodeSpacing": 30,
    "rankSpacing": 40
  },
  "themeVariables": {
    "fontFamily": "Arial",
    "fontSize": "14px",
    "primaryBorderColor": "#0f172a",
    "lineColor": "#2563eb",
    "tertiaryColor": "#ffffff"
  }
}}%%

flowchart LR

    linkStyle default stroke:#2563eb,stroke-width:4px;

    A["ACS<br/>Linux"]
    A --> B["• Linux<br/>  debug dump<br/>• Device driver<br/>  info"]
    B --> C["FWTS"]

    C --> D["BSA<br/>Linux"]

    C -->|"SBMR enabled"| E["SBMR<br/>in-band"]
    E --> D

    D --> F["• EDK2<br/>  test parser<br/>• Post<br/>  scripts"]

    D -->|"SBSA enabled"| G["SBSA<br/>Linux"]
    G --> F

    F --> H["ACS log parser<br/><br/>(apply waivers<br/>if configured)"]
    H --> I["Print<br/>ACS summary"]

    classDef entry fill:#dbeafe,stroke:#1d4ed8,stroke-width:3px,color:#0f172a;
    classDef linux fill:#dcfce7,stroke:#16a34a,stroke-width:3px,color:#0f172a;
    classDef result fill:#ede9fe,stroke:#7c3aed,stroke-width:3px,color:#0f172a;

    class A entry;
    class B,C,D,E,G linux;
    class F,H,I result;
```

---

### 3. Linux Automation Flow

> This flow is executed either after **SystemReady band ACS (Automation)** completes the UEFI phase, or directly when **Linux Boot** is selected from GRUB.

```mermaid
%%{init: {
  "theme": "base",
  "flowchart": {
    "curve": "linear",
    "nodeSpacing": 30,
    "rankSpacing": 40
  },
  "themeVariables": {
    "fontFamily": "Arial",
    "fontSize": "14px",
    "primaryBorderColor": "#0f172a",
    "lineColor": "#2563eb",
    "tertiaryColor": "#ffffff"
  }
}}%%

flowchart LR

    linkStyle default stroke:#2563eb,stroke-width:4px;

    A["ACS Linux<br/>Initialization"]
    A --> B["• Linux<br/>  debug dump<br/>• Device driver<br/>  info"]
    B --> C["FWTS"]

    C --> D["BSA<br/>Linux"]

    C -->|"SBMR enabled"| E["SBMR<br/>in-band"]
    E --> D

    D --> F["• EDK2<br/>  test parser<br/>• Post<br/>  scripts"]

    D -->|"SBSA enabled"| G["SBSA<br/>Linux"]
    G --> F

    F --> H["ACS log parser<br/><br/>(apply waivers<br/>if configured)"]
    H --> I["Print<br/>ACS summary"]

    classDef entry fill:#dbeafe,stroke:#1d4ed8,stroke-width:3px,color:#0f172a;
    classDef linux fill:#dcfce7,stroke:#16a34a,stroke-width:3px,color:#0f172a;
    classDef result fill:#ede9fe,stroke:#7c3aed,stroke-width:3px,color:#0f172a;

    class A entry;
    class B,C,D,E,G linux;
    class F,H,I result;
```

---

### 4. BBSR Automation Flow

> If Secure Boot keys are not provisioned automatically, provision the keys manually and then run the BBSR automation again.

```mermaid
%%{init: {
  "theme": "base",
  "flowchart": {
    "curve": "linear",
    "nodeSpacing": 30,
    "rankSpacing": 40
  },
  "themeVariables": {
    "fontFamily": "Arial",
    "fontSize": "14px",
    "primaryBorderColor": "#0f172a",
    "lineColor": "#2563eb",
    "tertiaryColor": "#ffffff"
  }
}}%%

flowchart LR

    linkStyle default stroke:#2563eb,stroke-width:4px;

    A["BBSR<br/>Compliance<br/><b>Automation</b>"]
    A --> B{"Secure Boot<br/>enabled?"}

    B -->|"yes"| D["BBSR<br/>UEFI / SCT<br/>flow"]
    B -->|"no"| C["Provision<br/>Secure Boot<br/>keys"]

    C --> D

    D --> E["Secure<br/>Linux boot"]
    E --> F["Collect<br/>BBSR logs<br/><br/>(FWTS / TPM)"]
    F --> G["ACS log parser<br/><br/>BBSR summary"]

    classDef bbsr fill:#fef3c7,stroke:#d97706,stroke-width:3px,color:#0f172a;
    classDef decision fill:#ffffff,stroke:#2563eb,stroke-width:3px,color:#0f172a;
    classDef linux fill:#dcfce7,stroke:#16a34a,stroke-width:3px,color:#0f172a;
    classDef result fill:#ede9fe,stroke:#7c3aed,stroke-width:3px,color:#0f172a;

    class A,C,D bbsr;
    class B decision;
    class E,F linux;
    class G result;
```
---
## GRUB Boot Menu Options

| Boot Option | Purpose |
|---|---|
| `Linux Boot` | Boots ACS Linux environment |
| `SystemReady band ACS (Automation)` | Runs the complete automated SR compliance flow |
| `BBSR Compliance (Automation)` | Runs Secure Boot / BBSR compliance flow |
| `UEFI Execution Environment` | Provides manual UEFI shell execution environment |
| `Linux Execution Environment` | Provides manual Linux-side execution environment |
| `Linux Boot with SetVirtualAddressMap enabled` | Debug or special Linux boot option |
---

## Configuration Files

| File | Description |
|---|---|
|[`acs_config.txt`](../common/config/acs_config.txt) | Contains ACS and specification version information |
|[`acs_run_config.init`](../common/config/acs_run_config.ini)  | Enables or disables test suites and passes test arguments |
|[`system_config.txt`](../common/config/system_config.txt)  | Contains platform details used in the final ACS report |

---
## Result Collection

ACS logs and summaries are stored under:
```text
acs_results_template/acs_results/
```

Final parsed reports are generated under:
```text
acs_results_template/acs_results/acs_summary/
```
--------------
*Copyright (c) 2026, Arm Limited and Contributors. All rights reserved.*
