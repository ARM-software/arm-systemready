# add chainloader

GRUB_BUILDIN = "boot linux ext2 fat serial part_msdos part_gpt normal \
                pgp gcry_sha512 gcry_rsa ntfs ntfscomp hfsplus help \
                terminal terminfo tpm lsefi gettext read search_fs_file \
                search_fs_uuid search_label \
                efi_gop iso9660 configfile search loadenv test chain"

