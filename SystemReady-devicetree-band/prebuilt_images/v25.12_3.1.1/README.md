# DeviceTree Band v3.1.1 — Main Release & Release Candidates

This README describes where to find the **main (GA) release** and **Release Candidates (RCx)**, and how to use the artifacts.


## **RC0 directory:** [`./RC0/`](./RC0/)  
  Contains image, changes and known issues.


## Using the Images

If an image is split (e.g., `…wic.xzaa`, `…wic.xzab`, …), concatenate then decompress:

```bash
# 1) Join parts (pattern A: xzaa/xzab/…)
cat systemready-dt_acs_live_image.wic.xza* > systemready-dt_acs_live_image.wic.xz

# 2) Decompress to .wic
xz -d systemready-dt_acs_live_image.wic.xz
# -> systemready-dt_acs_live_image.wic
```

---

## Feedback & Issues

When reporting, please include:
- The **version/RC** (e.g., *v3.1.1 RC0* or *GA*),  
- The **board/machine** and exact artifact name,  
- Logs (console output, test logs), and steps to reproduce.
