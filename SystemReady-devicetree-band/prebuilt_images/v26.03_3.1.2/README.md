# DeviceTree Band v3.1.2 — Main Release & Release Candidates

This README describes where to find the **main release** and **Release Candidates (RCx)**, and how to use the artifacts.

## Table of Contents
- [Main Release Image](#main-release-image)
- [Release Candidate Images](#release-candidate-images)
  - [RC0 ](#rc0-rc0)
- [Feedback & Issues](#feedback--issues)


## Main Release Image
The **DeviceTree Band v3.1.2** release is WIP

---

## Release Candidate Images

### **RC0** [`./RC0/`](./RC0/)  
  Contains image, changes and known issues.

#### Concat and decompress the Image for use

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
- The **version/RC** (e.g., *v3.1.2 RC0* or *v3.1.2*),  
- The **board/machine** and exact artifact name,  
- Logs (console output, test logs), and steps to reproduce.
