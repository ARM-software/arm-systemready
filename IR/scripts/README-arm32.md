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

