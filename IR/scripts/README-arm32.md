# SystemReady IR ACS for 32bit Arm paltforms

ACS live image for 32bit Arm architectures can be generated using arm
dedicated scripts:

1. Clone the arm-systemready repository <br />
 `git clone https://github.com/ARM-software/arm-systemready.git`

2. Navigate to the IR/scripts directory <br />
 `cd arm-systemready/IR/scripts`

3. Run get_source.sh with argument `arm` to download all related sources and tools for the build. Provide the sudo permission when prompted <br />
 `./build-scripts/get_source.sh arm` <br />

4. Run build-ir-live-image-arm.sh to build of the IR ACS live image:<br />
 `./build-scripts/build-ir-live-image-arm.sh`

5. If all the above steps are successful, the bootable image will be available at **/path-to-arm-systemready/IR/scripts/output/ir_acs_live_image.img.xz**

The image is generated in a compressed (.xz) format. The image must be uncompressed before they are used. For example:<br />
 `xzcat ./output/ir_acs_live_image.img.xz | dd conv=fdatasync of=/dev/sda`

## Verification

### Verification of the 32b IR image on QEMU Arm machine

#### Building the firmware and QEMU

The U-Boot firmware and QEMU can be built with
[Buildroot](https://buildroot.org/).

To download and build the firmware code, do the following:

```
git clone https://git.buildroot.net/buildroot -b 2023.05.x
cd buildroot
make qemu_arm_ebbr_defconfig
make
```

When the build completes, it generates the firmware file
`output/images/flash.bin`, comprising TF-A, OP-TEE and the U-Boot bootloader. A
QEMU executable is also generated at `output/host/bin/qemu-system-arm`.

Specific information for this Buildroot configuration is available in the file
`board/qemu/arm-ebbr/readme.txt`.

More information on Buildroot is available in [The Buildroot user
manual](https://buildroot.org/downloads/manual/manual.html).

#### Verifying the ACS-IR pre-built image

Launch the model using the following command:

```
./output/host/bin/qemu-system-arm \
    -bios output/images/flash.bin \
    -cpu cortex-a15 \
    -d unimp \
    -device virtio-blk-device,drive=hd1 \
    -device virtio-blk-device,drive=hd0 \
    -device virtio-net-device,netdev=eth0 \
    -device virtio-rng-device,rng=rng0 \
    -drive file=<path-to/ir_acs_live_image.img>,if=none,format=raw,id=hd0 \
    -drive file=output/images/disk.img,if=none,id=hd1 \
    -m 1024 \
    -machine virt,secure=on \
    -monitor null \
    -netdev user,id=eth0 \
    -no-acpi \
    -nodefaults \
    -nographic \
    -object rng-random,filename=/dev/urandom,id=rng0 \
    -rtc base=utc,clock=host \
    -serial stdio \
    -smp 2
```
