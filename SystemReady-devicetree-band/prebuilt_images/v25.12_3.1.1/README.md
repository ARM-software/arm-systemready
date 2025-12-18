# DeviceTree Band v3.1.1 — Main Release & Release Candidates

This README describes where to find the **main (GA) release** and **Release Candidates (RCx)**, and how to use the artifacts.

## Table of Contents
- [Main Release Image](#main-release-image)
- [Release Candidate Images](#release-candidate-images)
  - [RC0 ](#rc0-directory)
  - [RC-Final](#rc-final-directory)
- [Feedback & Issues](#feedback--issues)


## Main Release Image
The **DeviceTree Band v3.1.1** release pre-built image is available for download at:

🔗 [Download systemready-dt_acs_live_image.wic.xz](https://github.com/ARM-software/arm-systemready/releases/download/v25.12_DT_3.1.1/systemready-dt_acs_live_image.wic.xz)


### Unzip and Decompressing the Image for use

Follow the steps below to decompress the pre-built image:

```bash
xz -d systemready-dt_acs_live_image.wic.xz
```
After decompression, you will get the .wic file, which can be used directly with your target environment.

---

## Release Candidate Images

### **RC0 directory:** [`./RC0/`](./RC0/)  
  Contains image, changes and known issues.

### **RC-Final directory:** [`./RC-Final/`](./RC-Final/)  
  Contains image, changes and known issues.

#### Using the Images

If an image is split (e.g., `…wic.xzaa`, `…wic.xzab`, …), concatenate then decompress:

```bash
# 1) Join parts (pattern A: xzaa/xzab/…)
cat systemready-dt_acs_live_image.wic.xza* > systemready-dt_acs_live_image.wic.xz

# 2) Decompress to .wic
xz -d systemready-dt_acs_live_image.wic.xz
# -> systemready-dt_acs_live_image.wic
```

---

### Feedback & Issues

When reporting, please include:
- The **version/RC** (e.g., *v3.1.1 RC0* or *GA*),  
- The **board/machine** and exact artifact name,  
- Logs (console output, test logs), and steps to reproduce.
