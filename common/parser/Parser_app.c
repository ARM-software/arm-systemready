/** @file
 * Copyright (c) 2025, Arm Limited or its affiliates. All rights reserved.
 * SPDX-License-Identifier : Apache-2.0

 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *  http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 **/
 
 #include <Uefi.h>
 #include <Library/UefiBootServicesTableLib.h>
 #include <Library/UefiLib.h>
 #include <Library/ShellCEntryLib.h>
 #include <Library/ShellLib.h>
 #include <Protocol/SimpleFileSystem.h>
 #include <Guid/FileInfo.h>
 #include <Library/MemoryAllocationLib.h>
 #include <Library/BaseLib.h>
 #include <Library/BaseMemoryLib.h>
 #include <Library/UefiBootServicesTableLib.h>
 #include <Library/PrintLib.h>
 #include <Library/DevicePathLib.h>
 #include <Library/UefiRuntimeServicesTableLib.h>
 
 #define MAX_KEY_VALUE_PAIRS 20
 #define MAX_LINE_LENGTH 256
 #define CONFIG_FILE_NAME L"\\acs_tests\\config\\acs_run_config.ini"
 
 // Structure to hold BSA configuration
 typedef struct {
     BOOLEAN BsaEnabled;
     CHAR16* BsaModules;
     CHAR16* BsaTests;
     CHAR16* BsaSkip;
     CHAR16* BsaVerbose;
 } BSA_CONFIG;
 
 // Structure to hold SBSA configuration
 typedef struct
 {
     BOOLEAN SbsaEnabled;
     CHAR16 *SbsaModules;
     CHAR16 *SbsaLevel;
     CHAR16 *SbsaTests;
     CHAR16 *SbsaSkip;
     CHAR16 *SbsaVerboseMode;
 } SBSA_CONFIG;
 
 // Structure to hold SCT configuration
 typedef struct
 {
     BOOLEAN Enabled;
     BOOLEAN SctUiMode;
     CHAR16 *SequenceFile;
 } SCT_CONFIG;
 
 typedef struct
 {
     BOOLEAN BbsrSctEnabled;
     CHAR16 *SequenceFile;
 } BBSR_SCT_CONFIG;
 
 typedef struct
 {
     BOOLEAN Enabled;
 } GENERIC_CONFIG;
 
 typedef struct
 {
     BOOLEAN Enabled;
 } SCRT_CONFIG;
 
 EFI_STATUS ReadFileContent(IN EFI_FILE_PROTOCOL *File, OUT CHAR8 **Content, OUT UINTN *ContentSize);
 EFI_STATUS GetUserInput(OUT CHAR16 *Buffer, IN UINTN BufferSize);
 BSA_CONFIG *ParseBsaConfig(CHAR16 *ConfigFileContent);
 CHAR16 *GenerateBsaCommandString(BSA_CONFIG *BsaConfig);
 INTN EFIAPI run_bsa_logic(UINTN Argc, IN CHAR16 **Argv);
 SCT_CONFIG *ParseSctConfig(CHAR16 *ConfigFileContent);
 CHAR16 *GenerateSctCommandString(SCT_CONFIG *SctConfig);
 INTN EFIAPI run_sct_logic(UINTN Argc, IN CHAR16 **Argv);
 SBSA_CONFIG *ParseSbsaConfig(CHAR16 *ConfigFileContent);
 CHAR16 *GenerateSbsaCommandString(SBSA_CONFIG *SbsaConfig);
 INTN EFIAPI run_sbsa_logic(UINTN Argc, IN CHAR16 **Argv);
 GENERIC_CONFIG *ParseGenericConfig(CHAR16 *ConfigFileContent);
 INTN EFIAPI run_generic_logic(UINTN Argc, IN CHAR16 **Argv);
 SCRT_CONFIG *ParseScrtConfig(CHAR16 *ConfigFileContent);
 CHAR16 *GenerateScrtCommandString(SCRT_CONFIG *ScrtConfig);
 INTN EFIAPI run_scrt_logic(UINTN Argc, IN CHAR16 **Argv);
 BBSR_SCT_CONFIG *ParseBbsrSctConfig(CHAR16 *ConfigFileContent);
CHAR16 *GenerateBbsrSctCommandString(BBSR_SCT_CONFIG *BbsrSctConfig);
INTN EFIAPI run_bbsr_sct_logic(UINTN Argc, IN CHAR16 **Argv);
 EFI_STATUS LocateConfigFile(EFI_FILE_HANDLE *Root, EFI_FILE_HANDLE *File);
 
 EFI_STATUS ReadFileContent(IN EFI_FILE_PROTOCOL *File, OUT CHAR8 **Content, OUT UINTN *ContentSize)
 {
     EFI_STATUS Status;
     EFI_FILE_INFO *FileInfo;
     UINTN FileInfoSize = SIZE_OF_EFI_FILE_INFO + 200;
 
     FileInfo = AllocateZeroPool(FileInfoSize);
     if (FileInfo == NULL)
     {
         Print(L"Failed to allocate FileInfo buffer\n");
         return EFI_OUT_OF_RESOURCES;
     }
 
     Status = File->GetInfo(File, &gEfiFileInfoGuid, &FileInfoSize, FileInfo);
     if (EFI_ERROR(Status))
     {
         Print(L"Error getting file info: %r\n", Status);
         FreePool(FileInfo);
         return Status;
     }
 
     *ContentSize = (UINTN)FileInfo->FileSize;
     *Content = AllocateZeroPool(*ContentSize + sizeof(CHAR8));
     if (*Content == NULL)
     {
         Print(L"Failed to allocate buffer\n");
         FreePool(FileInfo);
         return EFI_OUT_OF_RESOURCES;
     }
 
     Status = File->Read(File, ContentSize, *Content);
     if (EFI_ERROR(Status))
     {
         Print(L"Error reading file: %r\n", Status);
         FreePool(*Content);
         FreePool(FileInfo);
         return Status;
     }
 
     (*Content)[*ContentSize / sizeof(CHAR8)] = '\0';
 
     FreePool(FileInfo);
     return EFI_SUCCESS;
 }
 
 EFI_STATUS GetUserInput(OUT CHAR16 *Buffer, IN UINTN BufferSize)
 {
     EFI_STATUS Status;
     EFI_INPUT_KEY Key;
     UINTN Index = 0;
 
     while (Index < BufferSize - 1)
     {
         Status = gST->ConIn->ReadKeyStroke(gST->ConIn, &Key);
         if (EFI_ERROR(Status))
         {
             continue;
         }
 
         // Handle Enter key (finish input)
         if (Key.UnicodeChar == CHAR_CARRIAGE_RETURN)
         {
             break;
         }
 
         // Handle Backspace key
         if (Key.UnicodeChar == CHAR_BACKSPACE)
         {
             if (Index > 0)
             {
                 Index--;
                 Print(L"\b \b"); // Move cursor back, overwrite with space, move cursor back again
             }
             continue;
         }
 
         // Add character to buffer and display it
         Buffer[Index++] = Key.UnicodeChar;
         Print(L"%c", Key.UnicodeChar);
     }
 
     Buffer[Index] = L'\0'; // Null-terminate the string
     Print(L"\n");
     return EFI_SUCCESS;
 }
 
 EFI_STATUS EditConfig(IN UINTN Argc,IN CHAR16 **Argv)
 {
     EFI_STATUS Status;
     EFI_HANDLE *Handles;
     UINTN HandleCount = 0;
 
     // Get the number of handles that match the gEfiLoadedImageProtocolGuid protocol
     Status = gBS->LocateHandle(
         ByProtocol,
         &gEfiLoadedImageProtocolGuid,
         NULL,
         &HandleCount,
         NULL);
     if (EFI_ERROR(Status) && Status != EFI_BUFFER_TOO_SMALL)
     {
         Print(L"Failed to locate handles: %r\n", Status);
         return Status;
     }
 
     // Allocate memory for the handles
     Handles = (EFI_HANDLE *)AllocatePool(HandleCount * sizeof(EFI_HANDLE));
     if (Handles == NULL)
     {
         Print(L"Failed to allocate memory for handles\n");
         return EFI_OUT_OF_RESOURCES;
     }
 
     // Get the handles that match the gEfiLoadedImageProtocolGuid protocol
     Status = gBS->LocateHandle(
         ByProtocol,
         &gEfiLoadedImageProtocolGuid,
         NULL,
         &HandleCount,
         Handles);
     if (EFI_ERROR(Status))
     {
         Print(L"Failed to locate handles: %r\n", Status);
         FreePool(Handles);
         return Status;
     }
 
     // Execute the command only once
     if (HandleCount > 0)
     {
         Status = ShellExecute(&Handles[0],
                               L"edit \\acs_tests\\config\\acs_run_config.ini",
                               FALSE,
                               NULL,
                               &Status);
         if (EFI_ERROR(Status))
         {
             Print(L"Failed to execute shell command: %r\n", Status);
         }
         else
         {
             Print(L"Shell command executed successfully.\n");
         }
     }
 
     // Free the memory allocated for the handles
     FreePool(Handles);
 
     return Status;
 }
 
 BSA_CONFIG* ParseBsaConfig(CHAR16* ConfigFileContent) {
     BSA_CONFIG* BsaConfig = NULL;
     CHAR16* Line = ConfigFileContent;
     BOOLEAN bsaSection = FALSE;
 
     // Allocate memory for BSA config
     BsaConfig = AllocateZeroPool(sizeof(BSA_CONFIG));
     if (BsaConfig == NULL) {
         Print(L"Error: Unable to allocate memory for BSA config\n");
         return NULL;
     }
 
     // Initialize BSA config
     BsaConfig->BsaEnabled = FALSE;
     BsaConfig->BsaModules = NULL;
     BsaConfig->BsaTests = NULL;
     BsaConfig->BsaSkip = NULL;
     BsaConfig->BsaVerbose = NULL;
 
     // Split config file content into lines
     while (*Line != L'\0') {
         // Find the end of the current line
         CHAR16* EndOfLine = Line;
         while (*EndOfLine != L'\n' && *EndOfLine != L'\0') {
             EndOfLine++;
         }
 
         // Create a temporary string for the current line
         UINTN LineLength = (UINTN)(EndOfLine - Line);
         CHAR16* TempLine = AllocatePool((LineLength + 1) * sizeof(CHAR16));
         if (TempLine == NULL) {
             Print(L"Error: Unable to allocate memory for temporary line\n");
             return NULL;
         }
         StrnCpyS(TempLine, (LineLength + 1), Line, LineLength);
         TempLine[LineLength] = L'\0'; // Ensure null-termination
 
         // Check if line starts with [BSA]
         if (StrnCmp(TempLine, L"[BSA]", 5) == 0) {
             bsaSection = TRUE;
         }
 
         if (bsaSection) {
             // Remove leading and trailing whitespaces
             CHAR16* StartOfLine = TempLine;
             while (*StartOfLine == L' ' || *StartOfLine == L'\t') {
                 StartOfLine++;
             }
             CHAR16* EndOfTempLine = StartOfLine;
             while (*EndOfTempLine != L'\0') {
                 EndOfTempLine++;
             }
             EndOfTempLine--;
             while (EndOfTempLine > StartOfLine && (*EndOfTempLine == L' ' || *EndOfTempLine == L'\t')) {
                 *EndOfTempLine = L'\0';
                 EndOfTempLine--;
             }
 
             // SbsaSkip empty lines
             if (*StartOfLine == L'\0') {
                 FreePool(TempLine);
                 if (*EndOfLine != L'\0') {
                     Line = EndOfLine + 1;
                 } else {
                     Print(L"Error: Unexpected end of file...\n");
                     break;
                 }
                 continue;
             }
 
             // Split line into key-value pair
             CHAR16* EqualSign = StartOfLine;
             while (*EqualSign != L'=' && *EqualSign != L'\0') {
                 EqualSign++;
             }
 
             if (*EqualSign == L'=') {
                 CHAR16* Key = StartOfLine;
                 *EqualSign = L'\0'; // Null-terminate the Key string
                 CHAR16* Value = EqualSign + 1;
 
                 // Remove leading and trailing whitespaces from key and value
                 while (*Key == L' ' || *Key == L'\t') {
                     Key++;
                 }
                 CHAR16* EndOfKey = Key;
                 while (*EndOfKey != L'\0') {
                     EndOfKey++;
                 }
                 EndOfKey--;
                 while (EndOfKey > Key && (*EndOfKey == L' ' || *EndOfKey == L'\t')) {
                     *EndOfKey = L'\0';
                     EndOfKey--;
                 }
 
                 while (*Value == L' ' || *Value == L'\t') {
                     Value++;
                 }
                 CHAR16* EndOfValue = Value;
                 while (*EndOfValue != L'\0') {
                     EndOfValue++;
                 }
                 EndOfValue--;
                 while (EndOfValue > Value && (*EndOfValue == L' ' || *EndOfValue == L'\t')) {
                     *EndOfValue = L'\0';
                     EndOfValue--;
                 }
 
                 // Handle key-value pairs
                 if (Value != NULL && *Value != L'\0') {
                     if (StrnCmp(Key, L"automation_bsa_run", 18) == 0) {
                         if (StrnCmp(Value, L"true", 4) == 0) {
                             BsaConfig->BsaEnabled = TRUE;
                         } else {
                             BsaConfig->BsaEnabled = FALSE;
                         }
                     } else if (StrnCmp(Key, L"bsa_modules", 11) == 0) {
                         BsaConfig->BsaModules = AllocatePool((StrLen(Value) + 1) * sizeof(CHAR16));
                         if (BsaConfig->BsaModules != NULL) {
                             StrCpyS(BsaConfig->BsaModules, (StrLen(Value) + 1), Value);
                         }
                     } else if (StrnCmp(Key, L"bsa_tests", 9) == 0) {
                         BsaConfig->BsaTests = AllocatePool((StrLen(Value) + 1) * sizeof(CHAR16));
                         if (BsaConfig->BsaTests != NULL) {
                             StrCpyS(BsaConfig->BsaTests, (StrLen(Value) + 1), Value);
                         }
                     } else if (StrnCmp(Key, L"bsa_skip", 8) == 0) {
                         BsaConfig->BsaSkip = AllocatePool((StrLen(Value) + 1) * sizeof(CHAR16));
                         if (BsaConfig->BsaSkip != NULL) {
                             StrCpyS(BsaConfig->BsaSkip, (StrLen(Value) + 1), Value);
                         }
                     } else if (StrnCmp(Key, L"bsa_verbose", 11) == 0) {
                         BsaConfig->BsaVerbose = AllocatePool((StrLen(Value) + 1) * sizeof(CHAR16));
                         if (BsaConfig->BsaVerbose != NULL) {
                             StrCpyS(BsaConfig->BsaVerbose, (StrLen(Value) + 1), Value);
                         }
                     }
                 }
             }
 
             FreePool(TempLine);
         } else {
             FreePool(TempLine);
         }
 
         // Move to the next line
         if (*EndOfLine != L'\0') {
             Line = EndOfLine + 1;
         } else {
             Print(L"Error: Unexpected end of file...\n");
             break;
         }
     }
     return BsaConfig;
 }
 
 CHAR16* GenerateBsaCommandString(BSA_CONFIG* BsaConfig) {
     CHAR16* CommandString = NULL;
     UINTN CommandStringLength = 0;

     // Always generate commands if the command flag is passed to parser.efi
     if (1) {
         CommandStringLength = StrLen(L"bsa.efi") + 1; // Base command + null terminator
 
         if (BsaConfig->BsaModules != NULL && *BsaConfig->BsaModules != L'\0') {
             CommandStringLength += StrLen(L" -m ") + StrLen(BsaConfig->BsaModules);
         }
         if (BsaConfig->BsaTests != NULL && *BsaConfig->BsaTests != L'\0') {
             CommandStringLength += StrLen(L" -t ") + StrLen(BsaConfig->BsaTests);
         }
         if (BsaConfig->BsaSkip != NULL && *BsaConfig->BsaSkip != L'\0') {
             CommandStringLength += StrLen(L" -skip ") + StrLen(BsaConfig->BsaSkip);
         }
         if (BsaConfig->BsaVerbose != NULL && *BsaConfig->BsaVerbose != L'\0') {
             CommandStringLength += StrLen(L" -v ") + StrLen(BsaConfig->BsaVerbose);
         }
 
         CommandString = AllocatePool(CommandStringLength * sizeof(CHAR16));
         if (CommandString == NULL) {
             Print(L"Error: Unable to allocate memory for command string\n");
             return NULL;
         }
 
 
         // Build the command string
         StrCpyS(CommandString, CommandStringLength, L"bsa.efi");
         if (BsaConfig->BsaModules != NULL && *BsaConfig->BsaModules != L'\0') {
             StrCatS(CommandString, CommandStringLength, L" -m ");
             StrCatS(CommandString, CommandStringLength, BsaConfig->BsaModules);
         }
         if (BsaConfig->BsaTests != NULL && *BsaConfig->BsaTests != L'\0') {
             StrCatS(CommandString, CommandStringLength, L" -t ");
             StrCatS(CommandString, CommandStringLength, BsaConfig->BsaTests);
         }
         if (BsaConfig->BsaSkip != NULL && *BsaConfig->BsaSkip != L'\0') {
             StrCatS(CommandString, CommandStringLength, L" -skip ");
             StrCatS(CommandString, CommandStringLength, BsaConfig->BsaSkip);
         }
         if (BsaConfig->BsaVerbose != NULL && *BsaConfig->BsaVerbose != L'\0') {
             StrCatS(CommandString, CommandStringLength, L" -v ");
             StrCatS(CommandString, CommandStringLength, BsaConfig->BsaVerbose);
         }
     }
 
     return CommandString;
 }
 
 INTN EFIAPI run_bsa_logic(UINTN Argc, IN CHAR16 **Argv) {
     EFI_STATUS Status;
     EFI_FILE_HANDLE Root = NULL, File = NULL;
     EFI_HANDLE *Handles = NULL;
     CHAR8 *Content = NULL;
     UINTN ContentSize = 0;
     CHAR16* ConfigFileContent = NULL;
 
     // Locate all the handles that support the Simple File System Protocol
    // Locate and open the config file
    Status = LocateConfigFile(&Root, &File);
    if (EFI_ERROR(Status))
    {
        Print(L"Failed to locate config file: %r\n", Status);
        return Status;
    }
     // Read the file content
     Status = ReadFileContent(File, &Content, &ContentSize);
     if (EFI_ERROR(Status)) {
         Print(L"Error reading file content: %r\n", Status);
         File->Close(File);
         Root->Close(Root);
         FreePool(Handles);
         return Status;
     }
 
     // Convert ASCII content to Unicode
     ConfigFileContent = AllocateZeroPool((AsciiStrLen(Content) + 1) * sizeof(CHAR16));
     AsciiStrToUnicodeStrS(Content, ConfigFileContent, AsciiStrLen(Content) + 1);
 
     // Parse BSA configuration
     BSA_CONFIG* BsaConfig = ParseBsaConfig(ConfigFileContent);
     if (BsaConfig == NULL) {
         Print(L"Failed to parse BSA configuration\n");
         FreePool(ConfigFileContent);
         FreePool(Content);
         File->Close(File);
         Root->Close(Root);
         FreePool(Handles);
         return EFI_OUT_OF_RESOURCES;
     }
 
     // Generate BSA command string
     CHAR16* BsaCommandString = GenerateBsaCommandString(BsaConfig);
     if (BsaCommandString == NULL) {
         Print(L"Failed to generate BSA command string\n");
         if (BsaConfig->BsaModules != NULL && *BsaConfig->BsaModules != L'\0') {
         FreePool(BsaConfig->BsaModules);
         }
         if (BsaConfig->BsaTests != NULL && *BsaConfig->BsaTests != L'\0') {
         FreePool(BsaConfig->BsaTests);
         }
         if (BsaConfig->BsaSkip != NULL && *BsaConfig->BsaSkip != L'\0') {
         FreePool(BsaConfig->BsaSkip);
         }
         if (BsaConfig->BsaVerbose != NULL && *BsaConfig->BsaVerbose != L'\0') {
         FreePool(BsaConfig->BsaVerbose);
         }
         FreePool(BsaConfig);
         FreePool(ConfigFileContent);
         FreePool(Content);
         File->Close(File);
         Root->Close(Root);
         FreePool(Handles);
         return EFI_OUT_OF_RESOURCES;
     }
 
     // Print the generated BSA command string
     Print(L"BSA Command String: %s\n", BsaCommandString);
     // Set BsaEnableDisable environment variable
     if (BsaConfig->BsaEnabled)
     {
         ShellSetEnvironmentVariable(L"automation_bsa_run", L"true", TRUE);
     }
     else
     {
         ShellSetEnvironmentVariable(L"automation_bsa_run", L"false", TRUE);
     }
 
     // Set the command string as an environment variable
     Status = ShellSetEnvironmentVariable(L"BsaCommand", BsaCommandString, TRUE);
     if (EFI_ERROR(Status))
     {
         Print(L"Failed to set environment variable: %r\n", Status);
         return (INTN)Status;
     }
     // Clean up
     //FreePool(BsaCommandString);
     if (BsaConfig->BsaModules != NULL && *BsaConfig->BsaModules != L'\0') {
     FreePool(BsaConfig->BsaModules);
     }
     if (BsaConfig->BsaTests != NULL && *BsaConfig->BsaTests != L'\0') {
     FreePool(BsaConfig->BsaTests);
     }
     if (BsaConfig->BsaSkip != NULL && *BsaConfig->BsaSkip != L'\0') {
     FreePool(BsaConfig->BsaSkip);
     }
     if (BsaConfig->BsaVerbose != NULL && *BsaConfig->BsaVerbose != L'\0') {
     FreePool(BsaConfig->BsaVerbose);
     }
     FreePool(BsaConfig);
     FreePool(ConfigFileContent);
     FreePool(Content);
     File->Close(File);
     Root->Close(Root);
     FreePool(Handles);
 
     return EFI_SUCCESS;
 }
 
 INTN EFIAPI run_sbsa_logic(UINTN Argc, IN CHAR16 **Argv)
 {
     EFI_STATUS Status;
     EFI_FILE_HANDLE Root = NULL, File = NULL;
     EFI_HANDLE *Handles = NULL;
     CHAR8 *Content = NULL;
     UINTN ContentSize = 0;
     CHAR16 *ConfigFileContent = NULL;
 
    // Locate and open the config file
    Status = LocateConfigFile(&Root, &File);
    if (EFI_ERROR(Status))
    {
        Print(L"Failed to locate config file: %r\n", Status);
        return Status;
    }
 
     // Read the file content
     Status = ReadFileContent(File, &Content, &ContentSize);
     if (EFI_ERROR(Status))
     {
         Print(L"Error reading file content: %r\n", Status);
         File->Close(File);
         Root->Close(Root);
         FreePool(Handles);
         return Status;
     }
 
     // Convert ASCII content to Unicode
     ConfigFileContent = AllocateZeroPool((AsciiStrLen(Content) + 1) * sizeof(CHAR16));
     AsciiStrToUnicodeStrS(Content, ConfigFileContent, AsciiStrLen(Content) + 1);
 
     // Parse SBSA configuration
     SBSA_CONFIG *SbsaConfig = ParseSbsaConfig(ConfigFileContent);
     if (SbsaConfig == NULL)
     {
         Print(L"Failed to parse SBSA configuration\n");
         FreePool(ConfigFileContent);
         FreePool(Content);
         File->Close(File);
         Root->Close(Root);
         FreePool(Handles);
         return EFI_OUT_OF_RESOURCES;
     }
 
     // Generate SBSA command string
     CHAR16 *SbsaCommandString = GenerateSbsaCommandString(SbsaConfig);
     if (SbsaCommandString == NULL)
     {
         Print(L"Failed to generate SBSA command string\n");
         if (SbsaConfig->SbsaModules != NULL && *SbsaConfig->SbsaModules != L'\0') {
         FreePool(SbsaConfig->SbsaModules);
         }
         if (SbsaConfig->SbsaLevel != NULL && *SbsaConfig->SbsaLevel != L'\0') {
         FreePool(SbsaConfig->SbsaLevel);
         }
         if (SbsaConfig->SbsaTests != NULL && *SbsaConfig->SbsaTests != L'\0') {
         FreePool(SbsaConfig->SbsaTests);
         }
         if (SbsaConfig->SbsaSkip != NULL && *SbsaConfig->SbsaSkip != L'\0') {
         FreePool(SbsaConfig->SbsaSkip);
         }
         if (SbsaConfig->SbsaVerboseMode != NULL && *SbsaConfig->SbsaVerboseMode != L'\0') {
         FreePool(SbsaConfig->SbsaVerboseMode);
         }
         FreePool(SbsaConfig);
         FreePool(ConfigFileContent);
         FreePool(Content);
         File->Close(File);
         Root->Close(Root);
         FreePool(Handles);
         return EFI_OUT_OF_RESOURCES;
     }
 
     // Print the generated SBSA command string
     Print(L"SBSA Command String: %s\n", SbsaCommandString);
 
     // Set SbsaEnableDisable environment variable
     if (SbsaConfig->SbsaEnabled)
     {
         ShellSetEnvironmentVariable(L"automation_sbsa_run", L"true", TRUE);
     }
     else
     {
         ShellSetEnvironmentVariable(L"automation_sbsa_run", L"false", TRUE);
     }
 
     // Set the command string as an environment variable
     Status = ShellSetEnvironmentVariable(L"SbsaCommand", SbsaCommandString, TRUE);
     if (EFI_ERROR(Status))
     {
         Print(L"Failed to set environment variable: %r\n", Status);
         return (INTN)Status;
     }
 
     // Clean up
     //FreePool(SbsaCommandString);
     if (SbsaConfig->SbsaModules != NULL && *SbsaConfig->SbsaModules != L'\0') {
     FreePool(SbsaConfig->SbsaModules);
     }
     if (SbsaConfig->SbsaLevel != NULL && *SbsaConfig->SbsaLevel != L'\0') {
     FreePool(SbsaConfig->SbsaLevel);
     }
     if (SbsaConfig->SbsaTests != NULL && *SbsaConfig->SbsaTests != L'\0') {
     FreePool(SbsaConfig->SbsaTests);
     }
     if (SbsaConfig->SbsaSkip != NULL && *SbsaConfig->SbsaSkip != L'\0') {
     FreePool(SbsaConfig->SbsaSkip);
     }
     if (SbsaConfig->SbsaVerboseMode != NULL && *SbsaConfig->SbsaVerboseMode != L'\0') {
     FreePool(SbsaConfig->SbsaVerboseMode);
     }
     FreePool(SbsaConfig);
     FreePool(ConfigFileContent);
     FreePool(Content);
     File->Close(File);
     Root->Close(Root);
     FreePool(Handles);
 
     return EFI_SUCCESS;
 }
 
 SBSA_CONFIG *ParseSbsaConfig(CHAR16 *ConfigFileContent)
 {
     SBSA_CONFIG *SbsaConfig = NULL;
     CHAR16 *Line = ConfigFileContent;
     BOOLEAN sbsaSection = FALSE;
 
     // Allocate memory for SBSA config
     SbsaConfig = AllocateZeroPool(sizeof(SBSA_CONFIG));
     if (SbsaConfig == NULL)
     {
         Print(L"Error: Unable to allocate memory for SBSA config\n");
         return NULL;
     }
 
     // Initialize SBSA config
     SbsaConfig->SbsaEnabled = FALSE;
     SbsaConfig->SbsaModules = NULL;
     SbsaConfig->SbsaLevel = NULL;
     SbsaConfig->SbsaTests = NULL;
     SbsaConfig->SbsaSkip = NULL;
     SbsaConfig->SbsaVerboseMode = NULL;
 
     // Split config file content into lines
     while (*Line != L'\0')
     {
         // Find the end of the current line
         CHAR16 *EndOfLine = Line;
         while (*EndOfLine != L'\n' && *EndOfLine != L'\0')
         {
             EndOfLine++;
         }
 
         // Create a temporary string for the current line
         UINTN LineLength = (UINTN)(EndOfLine - Line);
         CHAR16 *TempLine = AllocatePool((LineLength + 1) * sizeof(CHAR16));
         if (TempLine == NULL)
         {
             Print(L"Error: Unable to allocate memory for temporary line\n");
             return NULL;
         }
         StrnCpyS(TempLine, (LineLength + 1), Line, LineLength);
         TempLine[LineLength] = L'\0'; // Ensure null-termination
 
         // Check if line starts with [SBSA]
         if (StrnCmp(TempLine, L"[SBSA]", 6) == 0)
         {
             sbsaSection = TRUE;
         }
 
         if (sbsaSection)
         {
             // Remove leading and trailing whitespaces
             CHAR16 *StartOfLine = TempLine;
             while ((*StartOfLine == L' ') || (*StartOfLine == L'\t'))
             {
                 StartOfLine++;
             }
             CHAR16 *EndOfTempLine = StartOfLine;
             while (*EndOfTempLine != L'\0')
             {
                 EndOfTempLine++;
             }
             EndOfTempLine--;
             while ((EndOfTempLine > StartOfLine) && ((*EndOfTempLine == L' ') || (*EndOfTempLine == L'\t')))
             {
                 *EndOfTempLine = L'\0';
                 EndOfTempLine--;
             }
 
             // SbsaSkip empty lines
             if (*StartOfLine == L'\0')
             {
                 FreePool(TempLine);
                 if (*EndOfLine != L'\0')
                 {
                     Line = EndOfLine + 1;
                 }
                 else
                 {
                     Print(L"Error: Unexpected end of file...\n");
                     break;
                 }
                 continue;
             }
 
             // Split line into key-value pair
             CHAR16 *EqualSign = StartOfLine;
             while (*EqualSign != L'=' && *EqualSign != L'\0')
             {
                 EqualSign++;
             }
 
             if (*EqualSign == L'=')
             {
                 CHAR16 *Key = StartOfLine;
                 *EqualSign = L'\0'; // Null-terminate the Key string
                 CHAR16 *Value = EqualSign + 1;
 
                 // Remove leading and trailing whitespaces from key and value
                 while (*Value == L' ' || *Value == L'\t')
                 {
                     Value++;
                 }
                 CHAR16 *EndOfValue = Value;
                 while (*EndOfValue != L'\0')
                 {
                     EndOfValue++;
                 }
                 EndOfValue--;
                 while (EndOfValue > Value && (*EndOfValue == L' ' || *EndOfValue == L'\t'))
                 {
                     *EndOfValue = L'\0';
                     EndOfValue--;
                 }
 
                 // Handle key-value pairs
                 if (Value != NULL && *Value != L'\0')
                 {
                     if (StrnCmp(Key, L"automation_sbsa_run", 19) == 0)
                     {
                         if (StrnCmp(Value, L"true", 4) == 0)
                         {
                             SbsaConfig->SbsaEnabled = TRUE;
                         }
                         else
                         {
                             SbsaConfig->SbsaEnabled = FALSE;
                         }
                     }
                     else if (StrnCmp(Key, L"sbsa_modules", 12) == 0)
                     {
                         SbsaConfig->SbsaModules = AllocatePool((StrLen(Value) + 1) * sizeof(CHAR16));
                         if (SbsaConfig->SbsaModules != NULL)
                         {
                             StrCpyS(SbsaConfig->SbsaModules, (StrLen(Value) + 1), Value);
                         }
                     }
                     else if (StrnCmp(Key, L"sbsa_level", 10) == 0)
                     {
                         SbsaConfig->SbsaLevel = AllocatePool((StrLen(Value) + 1) * sizeof(CHAR16));
                         if (SbsaConfig->SbsaLevel != NULL)
                         {
                             StrCpyS(SbsaConfig->SbsaLevel, (StrLen(Value) + 1), Value);
                         }
                     }
                     else if (StrnCmp(Key, L"sbsa_tests", 10) == 0)
                     {
                         SbsaConfig->SbsaTests = AllocatePool((StrLen(Value) + 1) * sizeof(CHAR16));
                         if (SbsaConfig->SbsaTests != NULL)
                         {
                             StrCpyS(SbsaConfig->SbsaTests, (StrLen(Value) + 1), Value);
                         }
                     }
                     else if (StrnCmp(Key, L"sbsa_skip", 9) == 0)
                     {
                         SbsaConfig->SbsaSkip = AllocatePool((StrLen(Value) + 1) * sizeof(CHAR16));
                         if (SbsaConfig->SbsaSkip != NULL)
                         {
                             StrCpyS(SbsaConfig->SbsaSkip, (StrLen(Value) + 1), Value);
                         }
                     }
                     else if (StrnCmp(Key, L"sbsa_verbose", 12) == 0)
                     {
                         SbsaConfig->SbsaVerboseMode = AllocatePool((StrLen(Value) + 1) * sizeof(CHAR16));
                         if (SbsaConfig->SbsaVerboseMode != NULL)
                         {
                             StrCpyS(SbsaConfig->SbsaVerboseMode, (StrLen(Value) + 1), Value);
                         }
                     }
                 }
             }
 
             FreePool(TempLine);
         }
         else
         {
             FreePool(TempLine);
         }
 
         // Move to the next line
         if (*EndOfLine != L'\0')
         {
             Line = EndOfLine + 1;
         }
         else
         {
             Print(L"Error: Unexpected end of file...\n");
             break;
         }
     }
 
     return SbsaConfig;
 }
 
 CHAR16 *GenerateSbsaCommandString(SBSA_CONFIG *SbsaConfig)
 {
     CHAR16 *CommandString = NULL;
     UINTN CommandStringLength = 0;
 
     /* generate sbsa command always when -sbsa option is passed */
     if (1)
     {
 
         CommandStringLength = StrLen(L"sbsa.efi") + 1;
         if (SbsaConfig->SbsaModules != NULL && *SbsaConfig->SbsaModules != L'\0') {
             CommandStringLength += StrLen(L" -m ") + StrLen(SbsaConfig->SbsaModules);
         }
         if (SbsaConfig->SbsaLevel != NULL && *SbsaConfig->SbsaLevel != L'\0') {
             CommandStringLength += StrLen(L" -l ") + StrLen(SbsaConfig->SbsaLevel);
         }
         if (SbsaConfig->SbsaTests != NULL && *SbsaConfig->SbsaTests != L'\0') {
             CommandStringLength += StrLen(L" -t ") + StrLen(SbsaConfig->SbsaTests);
         }
         if (SbsaConfig->SbsaSkip != NULL && *SbsaConfig->SbsaSkip != L'\0') {
             CommandStringLength += StrLen(L" -skip ") + StrLen(SbsaConfig->SbsaSkip);
         }
         if (SbsaConfig->SbsaVerboseMode != NULL && *SbsaConfig->SbsaVerboseMode != L'\0') {
             CommandStringLength += StrLen(L" -v ") + StrLen(SbsaConfig->SbsaVerboseMode);
         }
         //                      StrLen(L" -m ") + StrLen(SbsaConfig->SbsaModules) +
         //                      StrLen(L" -l ") + StrLen(SbsaConfig->SbsaLevel) +
         //                      StrLen(L" -t ") + StrLen(SbsaConfig->SbsaTests) +
         //                      StrLen(L" -skip ") + StrLen(SbsaConfig->SbsaSkip) +
         //                      StrLen(L" ") + StrLen(SbsaConfig->SbsaVerboseMode) + 1;
 
         CommandString = AllocatePool(CommandStringLength * sizeof(CHAR16));
         if (CommandString == NULL)
         {
             return NULL;
         }
 
         StrCpyS(CommandString, CommandStringLength, L"sbsa.efi");
         if (SbsaConfig->SbsaModules != NULL && *SbsaConfig->SbsaModules != L'\0') {
         StrCatS(CommandString, CommandStringLength, L" -m ");
         StrCatS(CommandString, CommandStringLength, SbsaConfig->SbsaModules);
         }
         if (SbsaConfig->SbsaLevel != NULL && *SbsaConfig->SbsaLevel != L'\0') {
         StrCatS(CommandString, CommandStringLength, L" -l ");
         StrCatS(CommandString, CommandStringLength, SbsaConfig->SbsaLevel);
         }
         if (SbsaConfig->SbsaTests != NULL && *SbsaConfig->SbsaTests != L'\0') {
         StrCatS(CommandString, CommandStringLength, L" -t ");
         StrCatS(CommandString, CommandStringLength, SbsaConfig->SbsaTests);
         }
         if (SbsaConfig->SbsaSkip != NULL && *SbsaConfig->SbsaSkip != L'\0') {
         StrCatS(CommandString, CommandStringLength, L" -skip ");
         StrCatS(CommandString, CommandStringLength, SbsaConfig->SbsaSkip);
         }
         if (SbsaConfig->SbsaVerboseMode != NULL && *SbsaConfig->SbsaVerboseMode != L'\0') {
         StrCatS(CommandString, CommandStringLength, L" -v ");
         StrCatS(CommandString, CommandStringLength, SbsaConfig->SbsaVerboseMode);
         }
     }
 
     return CommandString;
 }
 
 SCT_CONFIG *ParseSctConfig(CHAR16 *ConfigFileContent){
     SCT_CONFIG *SctConfig = NULL;
     CHAR16 *Line = ConfigFileContent;
     BOOLEAN sctSection = FALSE;
 
     // Allocate memory for SCT config
     SctConfig = AllocateZeroPool(sizeof(SCT_CONFIG));
     if (SctConfig == NULL)
     {
         Print(L"Error: Unable to allocate memory for SCT config\n");
         return NULL;
     }
 
     // Initialize SCT config
     SctConfig->Enabled = FALSE;
     SctConfig->SequenceFile = NULL;
     SctConfig->SctUiMode = FALSE;
 
     // Split config file content into lines
     while (*Line != L'\0')
     {
         // Find the end of the current line
         CHAR16 *EndOfLine = Line;
         while (*EndOfLine != L'\n' && *EndOfLine != L'\0')
         {
             EndOfLine++;
         }
 
         // Create a temporary string for the current line
         UINTN LineLength = (UINTN)(EndOfLine - Line);
         CHAR16 *TempLine = AllocatePool((LineLength + 1) * sizeof(CHAR16));
         if (TempLine == NULL)
         {
             Print(L"Error: Unable to allocate memory for temporary line\n");
             return NULL;
         }
         StrnCpyS(TempLine, (LineLength + 1), Line, LineLength);
         TempLine[LineLength] = L'\0'; // Ensure null-termination
 
         // Check if line starts with [SCT]
         if (StrnCmp(TempLine, L"[SCT]", 5) == 0)
         {
             sctSection = TRUE;
         }
 
         if (sctSection)
         {
             // Remove leading and trailing whitespaces
             CHAR16 *StartOfLine = TempLine;
             while ((*StartOfLine == L' ') || (*StartOfLine == L'\t'))
             {
                 StartOfLine++;
             }
             CHAR16 *EndOfTempLine = StartOfLine;
             while (*EndOfTempLine != L'\0')
             {
                 EndOfTempLine++;
             }
             EndOfTempLine--;
             while ((EndOfTempLine > StartOfLine) && ((*EndOfTempLine == L' ') || (*EndOfTempLine == L'\t')))
             {
                 *EndOfTempLine = L'\0';
                 EndOfTempLine--;
             }
 
             // SbsaSkip empty lines
             if (*StartOfLine == L'\0')
             {
                 FreePool(TempLine);
                 if (*EndOfLine != L'\0')
                 {
                     Line = EndOfLine + 1;
                 }
                 else
                 {
                     Print(L"Error: Unexpected end of file...\n");
                     break;
                 }
                 continue;
             }
 
             // Split line into key-value pair
             CHAR16 *EqualSign = StartOfLine;
             while (*EqualSign != L'=' && *EqualSign != L'\0')
             {
                 EqualSign++;
             }
 
             if (*EqualSign == L'=')
             {
                 CHAR16 *Key = StartOfLine;
                 *EqualSign = L'\0'; // Null-terminate the Key string
                 CHAR16 *Value = EqualSign + 1;
 
                 // Remove leading and trailing whitespaces from key and value
                 CHAR16 *EndOfKey = Key;
                 while (*EndOfKey != L'\0')
                 {
                     EndOfKey++;
                 }
                 EndOfKey--;
                 while ((EndOfKey > Key) && ((*EndOfKey == L' ') || (*EndOfKey == L'\t')))
                 {
                     *EndOfKey = L'\0';
                     EndOfKey--;
                 }
 
                 CHAR16 *EndOfValue = Value;
                 while (*EndOfValue != L'\0')
                 {
                     EndOfValue++;
                 }
                 EndOfValue--; // Point to the last character of the string
 
                 while ((*Value == L' ') || (*Value == L'\t'))
                 {
                     Value++;
                 }
 
                 while ((EndOfValue > Value) && ((*EndOfValue == L' ') || (*EndOfValue == L'\t')))
                 {
                     *EndOfValue = L'\0';
                     EndOfValue--;
                 }
 
                 // Handle key-value pairs
                 if (Value != NULL && *Value != L'\0')
                 {
                     if (StrnCmp(Key, L"automation_sct_run", 18) == 0)
                     {
                         if (StrnCmp(Value, L"true", 4) == 0)
                         {
                             SctConfig->Enabled = TRUE;
                         }
                         else
                         {
                             SctConfig->Enabled = FALSE;
                         }
                     }
                     else if (StrnCmp(Key, L"sct_sequence_file", 17) == 0)
                     {
                         SctConfig->SequenceFile = AllocatePool((StrLen(Value) + 1) * sizeof(CHAR16));
                         if (SctConfig->SequenceFile != NULL)
                         {
                             StrCpyS(SctConfig->SequenceFile, (StrLen(Value) + 1), Value);
                         }
                     }
                     else if (StrnCmp(Key, L"sct_ui_mode", 11) == 0)
                     {
                         if (StrnCmp(Value, L"true", 4) == 0)
                         {
                             SctConfig->SctUiMode = TRUE;
                         }
                         else
                         {
                             SctConfig->SctUiMode = FALSE;
                         }
                     }
                 }
             }
 
             FreePool(TempLine);
         }
         else
         {
             FreePool(TempLine);
         }
 
         // Move to the next line
         if (*EndOfLine != L'\0')
         {
             Line = EndOfLine + 1;
         }
         else
         {
             Print(L"Error: Unexpected end of file...\n");
             break;
         }
     }
     return SctConfig;
 }
 
 CHAR16 *GenerateSctCommandString(SCT_CONFIG *SctConfig){
     CHAR16 *CommandString = NULL;
     UINTN CommandStringLength = 0;

     /* Always generate sct command when -sct flag is passed */
     if (1)
     { 
         if (SctConfig->SctUiMode)
         {
             CommandStringLength = StrLen(L"sct -u") + 1;
             CommandString = AllocatePool(CommandStringLength * sizeof(CHAR16));
             StrCpyS(CommandString, CommandStringLength, L"sct -u");
         }
         else
         {
             CommandStringLength = StrLen(L"sct -s ") + StrLen(SctConfig->SequenceFile) + 1;
             CommandString = AllocatePool(CommandStringLength * sizeof(CHAR16));
             StrCpyS(CommandString, CommandStringLength, L"sct -s ");
             StrCatS(CommandString, CommandStringLength, SctConfig->SequenceFile);
         }
     }

     return CommandString;
 }
 
 INTN EFIAPI run_sct_logic(UINTN Argc, IN CHAR16 **Argv){
     EFI_STATUS Status;
     EFI_FILE_HANDLE Root = NULL, File = NULL;
     EFI_HANDLE *Handles = NULL;
     CHAR8 *Content = NULL;
     UINTN ContentSize = 0;
     CHAR16 *ConfigFileContent = NULL;
 
    // Locate and open the config file
    Status = LocateConfigFile(&Root, &File);
    if (EFI_ERROR(Status))
    {
        Print(L"Failed to locate config file: %r\n", Status);
        return Status;
    }
 
     // Read the file content
     Status = ReadFileContent(File, &Content, &ContentSize);
     if (EFI_ERROR(Status))
     {
         Print(L"Error reading file content: %r\n", Status);
         File->Close(File);
         Root->Close(Root);
         FreePool(Handles);
         return Status;
     }
 
     // Convert ASCII content to Unicode
     ConfigFileContent = AllocateZeroPool((AsciiStrLen(Content) + 1) * sizeof(CHAR16));
     AsciiStrToUnicodeStrS(Content, ConfigFileContent, AsciiStrLen(Content) + 1);
 
     // Parse SCT configuration
     SCT_CONFIG *SctConfig = ParseSctConfig(ConfigFileContent);
     if (SctConfig == NULL)
     {
         Print(L"Failed to parse SCT configuration\n");
         FreePool(ConfigFileContent);
         FreePool(Content);
         File->Close(File);
         Root->Close(Root);
         FreePool(Handles);
         return EFI_OUT_OF_RESOURCES;
     }
 
     // Generate SCT command string
     CHAR16 *SctCommandString = GenerateSctCommandString(SctConfig);
     if (SctCommandString == NULL)
     {
         Print(L"Failed to generate SCT command string\n");
         FreePool(SctConfig->SequenceFile);
         FreePool(SctConfig);
         FreePool(ConfigFileContent);
         FreePool(Content);
         File->Close(File);
         Root->Close(Root);
         FreePool(Handles);
         return EFI_OUT_OF_RESOURCES;
     }
 
     // Print the generated SCT command string
     Print(L"SCT Command String: %s\n", SctCommandString);
 
     // Set SctEnableDisable environment variable
     if (SctConfig->Enabled)
     {
         ShellSetEnvironmentVariable(L"automation_sct_run", L"true", TRUE);
     }
     else
     {
         ShellSetEnvironmentVariable(L"automation_sct_run", L"false", TRUE);
     }
    // Set the command string as an environment variable
     Status = ShellSetEnvironmentVariable(L"SctCommand", SctCommandString, TRUE);
     if (EFI_ERROR(Status))
     {
         Print(L"Failed to set environment variable: %r\n", Status);
         return (INTN)Status;
     }
     // Clean up
     //FreePool(SctCommandString);
     FreePool(SctConfig->SequenceFile);
     FreePool(SctConfig);
     FreePool(ConfigFileContent);
     FreePool(Content);
     File->Close(File);
     Root->Close(Root);
     FreePool(Handles);
 
     return EFI_SUCCESS;
 }
 
 GENERIC_CONFIG *ParseGenericConfig(CHAR16 *ConfigFileContent){
     GENERIC_CONFIG *GenericConfig = NULL;
     CHAR16 *Line = ConfigFileContent;
     BOOLEAN genericSection = FALSE;
 
     // Allocate memory for SCT config
     GenericConfig = AllocateZeroPool(sizeof(GENERIC_CONFIG));
     if (GenericConfig == NULL)
     {
         Print(L"Error: Unable to allocate memory for SCT config\n");
         return NULL;
     }
 
     // Initialize SCT config
     GenericConfig->Enabled = FALSE;
 
     // Split config file content into lines
     while (*Line != L'\0')
     {
         // Find the end of the current line
         CHAR16 *EndOfLine = Line;
         while (*EndOfLine != L'\n' && *EndOfLine != L'\0')
         {
             EndOfLine++;
         }
 
         // Create a temporary string for the current line
         UINTN LineLength = (UINTN)(EndOfLine - Line);
         CHAR16 *TempLine = AllocatePool((LineLength + 1) * sizeof(CHAR16));
         if (TempLine == NULL)
         {
             Print(L"Error: Unable to allocate memory for temporary line\n");
             return NULL;
         }
         StrnCpyS(TempLine, (LineLength + 1), Line, LineLength);
         TempLine[LineLength] = L'\0'; // Ensure null-termination
 
         // Check if line starts with [GENERIC]
         if (StrnCmp(TempLine, L"[AUTOMATION]", 5) == 0)
         {
             genericSection = TRUE;
         }
 
         if (genericSection)
         {
             // Remove leading and trailing whitespaces
             CHAR16 *StartOfLine = TempLine;
             while ((*StartOfLine == L' ') || (*StartOfLine == L'\t'))
             {
                 StartOfLine++;
             }
             CHAR16 *EndOfTempLine = StartOfLine;
             while (*EndOfTempLine != L'\0')
             {
                 EndOfTempLine++;
             }
             EndOfTempLine--;
             while ((EndOfTempLine > StartOfLine) && ((*EndOfTempLine == L' ') || (*EndOfTempLine == L'\t')))
             {
                 *EndOfTempLine = L'\0';
                 EndOfTempLine--;
             }
 
             // SbsaSkip empty lines
             if (*StartOfLine == L'\0')
             {
                 FreePool(TempLine);
                 if (*EndOfLine != L'\0')
                 {
                     Line = EndOfLine + 1;
                 }
                 else
                 {
                     Print(L"Error: Unexpected end of file...\n");
                     break;
                 }
                 continue;
             }
 
             // Split line into key-value pair
             CHAR16 *EqualSign = StartOfLine;
             while (*EqualSign != L'=' && *EqualSign != L'\0')
             {
                 EqualSign++;
             }
 
             if (*EqualSign == L'=')
             {
                 CHAR16 *Key = StartOfLine;
                 *EqualSign = L'\0'; // Null-terminate the Key string
                 CHAR16 *Value = EqualSign + 1;
 
                 // Remove leading and trailing whitespaces from key and value
                 CHAR16 *EndOfKey = Key;
                 while (*EndOfKey != L'\0')
                 {
                     EndOfKey++;
                 }
                 EndOfKey--;
                 while ((EndOfKey > Key) && ((*EndOfKey == L' ') || (*EndOfKey == L'\t')))
                 {
                     *EndOfKey = L'\0';
                     EndOfKey--;
                 }
 
                 CHAR16 *EndOfValue = Value;
                 while (*EndOfValue != L'\0')
                 {
                     EndOfValue++;
                 }
                 EndOfValue--; // Point to the last character of the string
 
                 while ((*Value == L' ') || (*Value == L'\t'))
                 {
                     Value++;
                 }
 
                 while ((EndOfValue > Value) && ((*EndOfValue == L' ') || (*EndOfValue == L'\t')))
                 {
                     *EndOfValue = L'\0';
                     EndOfValue--;
                 }
 
                 // Handle key-value pairs
                 if (Value != NULL && *Value != L'\0')
                 {
                     if (StrnCmp(Key, L"config_enabled_for_automation_run", 33) == 0)
                     {
                         if (StrnCmp(Value, L"true", 4) == 0)
                         {
                             GenericConfig->Enabled = TRUE;
                         }
                         else
                         {
                             GenericConfig->Enabled = FALSE;
                         }
                     }
                 }
             }
 
             FreePool(TempLine);
         }
         else
         {
             FreePool(TempLine);
         }
 
         // Move to the next line
         if (*EndOfLine != L'\0')
         {
             Line = EndOfLine + 1;
         }
         else
         {
             Print(L"Error: Unexpected end of file...\n");
             break;
         }
     }
     return GenericConfig;
 }
 
 INTN EFIAPI run_generic_logic(UINTN Argc, IN CHAR16 **Argv){
     EFI_STATUS Status;
     EFI_FILE_HANDLE Root = NULL, File = NULL;
     EFI_HANDLE *Handles = NULL;
     CHAR8 *Content = NULL;
     UINTN ContentSize = 0;
     CHAR16 *ConfigFileContent = NULL;
 
    // Locate and open the config file
    Status = LocateConfigFile(&Root, &File);
    if (EFI_ERROR(Status))
    {
        Print(L"Failed to locate config file: %r\n", Status);
        return Status;
    }
     // Read the file content
     Status = ReadFileContent(File, &Content, &ContentSize);
     if (EFI_ERROR(Status))
     {
         Print(L"Error reading file content: %r\n", Status);
         File->Close(File);
         Root->Close(Root);
         FreePool(Handles);
         return Status;
     }
 
     // Convert ASCII content to Unicode
     ConfigFileContent = AllocateZeroPool((AsciiStrLen(Content) + 1) * sizeof(CHAR16));
     AsciiStrToUnicodeStrS(Content, ConfigFileContent, AsciiStrLen(Content) + 1);
 
     // Parse SCT configuration
     GENERIC_CONFIG *GenericConfig = ParseGenericConfig(ConfigFileContent);
     if (GenericConfig == NULL)
     {
         Print(L"Failed to parse SCT configuration\n");
         FreePool(ConfigFileContent);
         FreePool(Content);
         File->Close(File);
         Root->Close(Root);
         FreePool(Handles);
         return EFI_OUT_OF_RESOURCES;
     }
 
     // Set SctEnableDisable environment variable
     if (GenericConfig->Enabled)
     {
         ShellSetEnvironmentVariable(L"config_enabled_for_automation_run", L"true", TRUE);
     }
     else
     {
         ShellSetEnvironmentVariable(L"config_enabled_for_automation_run", L"false", TRUE);
     } return (INTN)Status;
     
     FreePool(GenericConfig);
     FreePool(ConfigFileContent);
     FreePool(Content);
     File->Close(File);
     Root->Close(Root);
     FreePool(Handles);
 
     return EFI_SUCCESS;
 }
 
 SCRT_CONFIG *ParseScrtConfig(CHAR16 *ConfigFileContent){
     SCRT_CONFIG *ScrtConfig = NULL;
     CHAR16 *Line = ConfigFileContent;
     BOOLEAN scrtSection = FALSE;
 
     // Allocate memory for SCT config
     ScrtConfig = AllocateZeroPool(sizeof(SCRT_CONFIG));
     if (ScrtConfig == NULL)
     {
         Print(L"Error: Unable to allocate memory for SCT config\n");
         return NULL;
     }
 
     // Initialize SCT config
     ScrtConfig->Enabled = FALSE;
 
     // Split config file content into lines
     while (*Line != L'\0')
     {
         // Find the end of the current line
         CHAR16 *EndOfLine = Line;
         while (*EndOfLine != L'\n' && *EndOfLine != L'\0')
         {
             EndOfLine++;
         }
 
         // Create a temporary string for the current line
         UINTN LineLength = (UINTN)(EndOfLine - Line);
         CHAR16 *TempLine = AllocatePool((LineLength + 1) * sizeof(CHAR16));
         if (TempLine == NULL)
         {
             Print(L"Error: Unable to allocate memory for temporary line\n");
             return NULL;
         }
         StrnCpyS(TempLine, (LineLength + 1), Line, LineLength);
         TempLine[LineLength] = L'\0'; // Ensure null-termination
 
         // Check if line starts with [SCRT]
         if (StrnCmp(TempLine, L"[AUTOMATION]", 5) == 0)
         {
             scrtSection = TRUE;
         }
 
         if (scrtSection)
         {
             // Remove leading and trailing whitespaces
             CHAR16 *StartOfLine = TempLine;
             while ((*StartOfLine == L' ') || (*StartOfLine == L'\t'))
             {
                 StartOfLine++;
             }
             CHAR16 *EndOfTempLine = StartOfLine;
             while (*EndOfTempLine != L'\0')
             {
                 EndOfTempLine++;
             }
             EndOfTempLine--;
             while ((EndOfTempLine > StartOfLine) && ((*EndOfTempLine == L' ') || (*EndOfTempLine == L'\t')))
             {
                 *EndOfTempLine = L'\0';
                 EndOfTempLine--;
             }
 
             // SbsaSkip empty lines
             if (*StartOfLine == L'\0')
             {
                 FreePool(TempLine);
                 if (*EndOfLine != L'\0')
                 {
                     Line = EndOfLine + 1;
                 }
                 else
                 {
                     Print(L"Error: Unexpected end of file...\n");
                     break;
                 }
                 continue;
             }
 
             // Split line into key-value pair
             CHAR16 *EqualSign = StartOfLine;
             while (*EqualSign != L'=' && *EqualSign != L'\0')
             {
                 EqualSign++;
             }
 
             if (*EqualSign == L'=')
             {
                 CHAR16 *Key = StartOfLine;
                 *EqualSign = L'\0'; // Null-terminate the Key string
                 CHAR16 *Value = EqualSign + 1;
 
                 // Remove leading and trailing whitespaces from key and value
                 CHAR16 *EndOfKey = Key;
                 while (*EndOfKey != L'\0')
                 {
                     EndOfKey++;
                 }
                 EndOfKey--;
                 while ((EndOfKey > Key) && ((*EndOfKey == L' ') || (*EndOfKey == L'\t')))
                 {
                     *EndOfKey = L'\0';
                     EndOfKey--;
                 }
 
                 CHAR16 *EndOfValue = Value;
                 while (*EndOfValue != L'\0')
                 {
                     EndOfValue++;
                 }
                 EndOfValue--; // Point to the last character of the string
 
                 while ((*Value == L' ') || (*Value == L'\t'))
                 {
                     Value++;
                 }
 
                 while ((EndOfValue > Value) && ((*EndOfValue == L' ') || (*EndOfValue == L'\t')))
                 {
                     *EndOfValue = L'\0';
                     EndOfValue--;
                 }
 
                 // Handle key-value pairs
                 if (Value != NULL && *Value != L'\0')
                 {
                     if (StrnCmp(Key, L"automation_scrt_run", 19) == 0)
                     {
                         if (StrnCmp(Value, L"true", 4) == 0)
                         {
                             ScrtConfig->Enabled = TRUE;
                         }
                         else
                         {
                             ScrtConfig->Enabled = FALSE;
                         }
                     }
                 }
             }
 
             FreePool(TempLine);
         }
         else
         {
             FreePool(TempLine);
         }
 
         // Move to the next line
         if (*EndOfLine != L'\0')
         {
             Line = EndOfLine + 1;
         }
         else
         {
             Print(L"Error: Unexpected end of file...\n");
             break;
         }
     }
     return ScrtConfig;
 }
 
 INTN EFIAPI run_scrt_logic(UINTN Argc, IN CHAR16 **Argv){
     EFI_STATUS Status;
     EFI_FILE_HANDLE Root = NULL, File = NULL;
     EFI_HANDLE *Handles = NULL;
     CHAR8 *Content = NULL;
     UINTN ContentSize = 0;
     CHAR16 *ConfigFileContent = NULL;
 
    // Locate and open the config file
    Status = LocateConfigFile(&Root, &File);
    if (EFI_ERROR(Status))
    {
        Print(L"Failed to locate config file: %r\n", Status);
        return Status;
    }
 
     // Read the file content
     Status = ReadFileContent(File, &Content, &ContentSize);
     if (EFI_ERROR(Status))
     {
         Print(L"Error reading file content: %r\n", Status);
         File->Close(File);
         Root->Close(Root);
         FreePool(Handles);
         return Status;
     }
 
     // Convert ASCII content to Unicode
     ConfigFileContent = AllocateZeroPool((AsciiStrLen(Content) + 1) * sizeof(CHAR16));
     AsciiStrToUnicodeStrS(Content, ConfigFileContent, AsciiStrLen(Content) + 1);
 
     // Parse SCT configuration
     SCRT_CONFIG *ScrtConfig = ParseScrtConfig(ConfigFileContent);
     if (ScrtConfig == NULL)
     {
         Print(L"Failed to parse SCT configuration\n");
         FreePool(ConfigFileContent);
         FreePool(Content);
         File->Close(File);
         Root->Close(Root);
         FreePool(Handles);
         return EFI_OUT_OF_RESOURCES;
     }
 
     // Set SctEnableDisable environment variable
     if (ScrtConfig->Enabled)
     {
         ShellSetEnvironmentVariable(L"automation_scrt_run", L"true", TRUE);
     }
     else
     {
         ShellSetEnvironmentVariable(L"automation_scrt_run", L"false", TRUE);
     } return (INTN)Status;
     
     FreePool(ScrtConfig);
     FreePool(ConfigFileContent);
     FreePool(Content);
     File->Close(File);
     Root->Close(Root);
     FreePool(Handles);
 
     return EFI_SUCCESS;
 }


 BBSR_SCT_CONFIG *ParseBbsrSctConfig(CHAR16 *ConfigFileContent){
    BBSR_SCT_CONFIG *BbsrSctConfig = NULL;
    CHAR16 *Line = ConfigFileContent;
    BOOLEAN bbsrsctSection = FALSE;

    // Allocate memory for BBSR_SCT config
    BbsrSctConfig = AllocateZeroPool(sizeof(BBSR_SCT_CONFIG));
    if (BbsrSctConfig == NULL)
    {
        Print(L"Error: Unable to allocate memory for BBSR_SCT config\n");
        return NULL;
    }

    // Initialize BBSR_SCT config
    BbsrSctConfig->BbsrSctEnabled = FALSE;
    BbsrSctConfig->SequenceFile = NULL;

    // Split config file content into lines
    while (*Line != L'\0')
    {
        // Find the end of the current line
        CHAR16 *EndOfLine = Line;
        while (*EndOfLine != L'\n' && *EndOfLine != L'\0')
        {
            EndOfLine++;
        }

        // Create a temporary string for the current line
        UINTN LineLength = (UINTN)(EndOfLine - Line);
        CHAR16 *TempLine = AllocatePool((LineLength + 1) * sizeof(CHAR16));
        if (TempLine == NULL)
        {
            Print(L"Error: Unable to allocate memory for temporary line\n");
            return NULL;
        }
        StrnCpyS(TempLine, (LineLength + 1), Line, LineLength);
        TempLine[LineLength] = L'\0'; // Ensure null-termination

        // Check if line starts with [BBSR_SCT]
        if (StrnCmp(TempLine, L"[BBSR_SCT]", 5) == 0)
        {
            bbsrsctSection = TRUE;
        }

        if (bbsrsctSection)
        {
            // Remove leading and trailing whitespaces
            CHAR16 *StartOfLine = TempLine;
            while ((*StartOfLine == L' ') || (*StartOfLine == L'\t'))
            {
                StartOfLine++;
            }
            CHAR16 *EndOfTempLine = StartOfLine;
            while (*EndOfTempLine != L'\0')
            {
                EndOfTempLine++;
            }
            EndOfTempLine--;
            while ((EndOfTempLine > StartOfLine) && ((*EndOfTempLine == L' ') || (*EndOfTempLine == L'\t')))
            {
                *EndOfTempLine = L'\0';
                EndOfTempLine--;
            }

            // SbsaSkip empty lines
            if (*StartOfLine == L'\0')
            {
                FreePool(TempLine);
                if (*EndOfLine != L'\0')
                {
                    Line = EndOfLine + 1;
                }
                else
                {
                    Print(L"Error: Unexpected end of file...\n");
                    break;
                }
                continue;
            }

            // Split line into key-value pair
            CHAR16 *EqualSign = StartOfLine;
            while (*EqualSign != L'=' && *EqualSign != L'\0')
            {
                EqualSign++;
            }

            if (*EqualSign == L'=')
            {
                CHAR16 *Key = StartOfLine;
                *EqualSign = L'\0'; // Null-terminate the Key string
                CHAR16 *Value = EqualSign + 1;

                // Remove leading and trailing whitespaces from key and value
                CHAR16 *EndOfKey = Key;
                while (*EndOfKey != L'\0')
                {
                    EndOfKey++;
                }
                EndOfKey--;
                while ((EndOfKey > Key) && ((*EndOfKey == L' ') || (*EndOfKey == L'\t')))
                {
                    *EndOfKey = L'\0';
                    EndOfKey--;
                }

                CHAR16 *EndOfValue = Value;
                while (*EndOfValue != L'\0')
                {
                    EndOfValue++;
                }
                EndOfValue--; // Point to the last character of the string

                while ((*Value == L' ') || (*Value == L'\t'))
                {
                    Value++;
                }

                while ((EndOfValue > Value) && ((*EndOfValue == L' ') || (*EndOfValue == L'\t')))
                {
                    *EndOfValue = L'\0';
                    EndOfValue--;
                }

                // Handle key-value pairs
                if (Value != NULL && *Value != L'\0')
                {
                    if (StrnCmp(Key, L"automation_bbsr_sct_run", 23) == 0)
                    {
                        if (StrnCmp(Value, L"true", 4) == 0)
                        {
                            BbsrSctConfig->BbsrSctEnabled = TRUE;
                        }
                        else
                        {
                            BbsrSctConfig->BbsrSctEnabled = FALSE;
                        }
                    }
                    else if (StrnCmp(Key, L"bbsr_sct_sequence_file", 22) == 0)
                    {
                        BbsrSctConfig->SequenceFile = AllocatePool((StrLen(Value) + 1) * sizeof(CHAR16));
                        if (BbsrSctConfig->SequenceFile != NULL)
                        {
                            StrCpyS(BbsrSctConfig->SequenceFile, (StrLen(Value) + 1), Value);
                        }
                    }
                }
            }

            FreePool(TempLine);
        }
        else
        {
            FreePool(TempLine);
        }

        // Move to the next line
        if (*EndOfLine != L'\0')
        {
            Line = EndOfLine + 1;
        }
        else
        {
            Print(L"Error: Unexpected end of file...\n");
            break;
        }
    }
    return BbsrSctConfig;
}

CHAR16 *GenerateBbsrSctCommandString(BBSR_SCT_CONFIG *BbsrSctConfig){
    CHAR16 *CommandString = NULL;
    UINTN CommandStringLength = 0;

    CommandStringLength = StrLen(L"sct -s ") + StrLen(BbsrSctConfig->SequenceFile) + 1;
    CommandString = AllocatePool(CommandStringLength * sizeof(CHAR16));
    StrCpyS(CommandString, CommandStringLength, L"sct -s ");
    StrCatS(CommandString, CommandStringLength, BbsrSctConfig->SequenceFile);

    return CommandString;
}

INTN EFIAPI run_bbsr_sct_logic(UINTN Argc, IN CHAR16 **Argv){
    EFI_STATUS Status;
    EFI_FILE_HANDLE Root = NULL, File = NULL;
    EFI_HANDLE *Handles = NULL;
    CHAR8 *Content = NULL;
    UINTN ContentSize = 0;
    CHAR16 *ConfigFileContent = NULL;

   // Locate and open the config file
   Status = LocateConfigFile(&Root, &File);
   if (EFI_ERROR(Status))
   {
       Print(L"Failed to locate config file: %r\n", Status);
       return Status;
   }

    // Read the file content
    Status = ReadFileContent(File, &Content, &ContentSize);
    if (EFI_ERROR(Status))
    {
        Print(L"Error reading file content: %r\n", Status);
        File->Close(File);
        Root->Close(Root);
        FreePool(Handles);
        return Status;
    }

    // Convert ASCII content to Unicode
    ConfigFileContent = AllocateZeroPool((AsciiStrLen(Content) + 1) * sizeof(CHAR16));
    AsciiStrToUnicodeStrS(Content, ConfigFileContent, AsciiStrLen(Content) + 1);

    // Parse BBSR_SCT configuration
    BBSR_SCT_CONFIG *BbsrSctConfig = ParseBbsrSctConfig(ConfigFileContent);
    if (BbsrSctConfig == NULL)
    {
        Print(L"Failed to parse BBSR_SCT configuration\n");
        FreePool(ConfigFileContent);
        FreePool(Content);
        File->Close(File);
        Root->Close(Root);
        FreePool(Handles);
        return EFI_OUT_OF_RESOURCES;
    }

    // Generate BBSR_SCT command string
    CHAR16 *BbsrSctCommandString = GenerateBbsrSctCommandString(BbsrSctConfig);
    if (BbsrSctCommandString == NULL)
    {
        Print(L"Failed to generate BBSR_SCT command string\n");
        FreePool(BbsrSctConfig->SequenceFile);
        FreePool(BbsrSctConfig);
        FreePool(ConfigFileContent);
        FreePool(Content);
        File->Close(File);
        Root->Close(Root);
        FreePool(Handles);
        return EFI_OUT_OF_RESOURCES;
    }

    // Print the generated BBSR_SCT command string
    Print(L"BBSR_SCT Command String: %s\n", BbsrSctCommandString);

    // Set BbsrSctEnableDisable environment variable
    if (BbsrSctConfig->BbsrSctEnabled)
    {
        ShellSetEnvironmentVariable(L"automation_bbsr_sct_run", L"true", TRUE);
    }
    else
    {
        ShellSetEnvironmentVariable(L"automation_bbsr_sct_run", L"false", TRUE);
    }
   // Set the command string as an environment variable
    Status = ShellSetEnvironmentVariable(L"BbsrSctCommand", BbsrSctCommandString, TRUE);
    if (EFI_ERROR(Status))
    {
        Print(L"Failed to set environment variable: %r\n", Status);
        return (INTN)Status;
    }
    // Clean up
    //FreePool(BbsrSctCommandString);
    FreePool(BbsrSctConfig->SequenceFile);
    FreePool(BbsrSctConfig);
    FreePool(ConfigFileContent);
    FreePool(Content);
    File->Close(File);
    Root->Close(Root);
    FreePool(Handles);

    return EFI_SUCCESS;
}

 EFI_STATUS LocateConfigFile(EFI_FILE_HANDLE *Root, EFI_FILE_HANDLE *File)
 {
     EFI_STATUS Status;
     UINTN HandleCount;
     EFI_HANDLE *Handles;
     EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *Volume;
     EFI_FILE_HANDLE RootDir;
     UINTN i;
 
     // Locate all file system handles
     Status = gBS->LocateHandleBuffer(ByProtocol, &gEfiSimpleFileSystemProtocolGuid, NULL, &HandleCount, &Handles);
     if (EFI_ERROR(Status) || HandleCount == 0)
     {
         Print(L"Error locating file system handles: %r\n", Status);
         return Status;
     }
 
     // Iterate through all partitions
     for (i = 0; i < HandleCount; i++)
     {
         Status = gBS->HandleProtocol(Handles[i], &gEfiSimpleFileSystemProtocolGuid, (VOID **)&Volume);
         if (EFI_ERROR(Status))
         {
             Print(L"Error handling file system protocol on partition %d: %r\n", i, Status);
             continue;
         }
 
         // Open the volume
         Status = Volume->OpenVolume(Volume, &RootDir);
         if (EFI_ERROR(Status))
         {
             Print(L"Error opening volume on partition %d: %r\n", i, Status);
             continue;
         }
 
         // Try opening the configuration file
         Status = RootDir->Open(RootDir, File, CONFIG_FILE_NAME, EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE, 0);
         if (!EFI_ERROR(Status))
         {
             *Root = RootDir; // Save the correct partition root
             FreePool(Handles);
             return EFI_SUCCESS;
         }
         else
         {
             RootDir->Close(RootDir);
         }
     }
 
     // If we reach here, config file was not found on any partition
     Print(L"Config file not found on any partition.\n");
     FreePool(Handles);
     return EFI_NOT_FOUND;
 }
 
 INTN EFIAPI ShellAppMain(IN UINTN Argc, IN CHAR16 **Argv)
 {
     EFI_STATUS Status;
     SHELL_FILE_HANDLE FileHandle;

     // Attempt to open the config file
     Status = ShellOpenFileByName(CONFIG_FILE_NAME, &FileHandle, EFI_FILE_MODE_READ, 0);
     if (EFI_ERROR(Status)) {
         Print(L"Error: Config file not found at %s\n", CONFIG_FILE_NAME);
         return Status; // Return error if file is missing
     }
 
     // Close the file since it exists
     ShellCloseFile(&FileHandle);

     if (Argc == 1)
     {
         EFI_STATUS Status;
         EFI_FILE_HANDLE Root = NULL, File = NULL;
         EFI_HANDLE *Handles = NULL;
         CHAR8 *Content = NULL;
         UINTN ContentSize = 0;
         UINTN Index;
         EFI_INPUT_KEY KeyInput;
 
         // Locate all the handles that support the Simple File System Protocol
    // Locate and open the config file
    Status = LocateConfigFile(&Root, &File);
    if (EFI_ERROR(Status))
    {
        Print(L"Failed to locate config file: %r\n", Status);
        return Status;
    }

 
         // Print(L"\nFull Config File Content:\n\n%a\n", Content);
 
         while (TRUE)
         {
             Print(L"\nOptions:\n");
             Print(L"1. View Config\n");
             Print(L"2. Update Config\n");
             Print(L"3. Exit\n");
             Print(L"Enter your choice: ");
 
             gBS->WaitForEvent(1, &gST->ConIn->WaitForKey, &Index);
             gST->ConIn->ReadKeyStroke(gST->ConIn, &KeyInput);
 
             switch (KeyInput.UnicodeChar)
             {
             case '1':
                 // Open the configuration file
                 Status = Root->Open(Root, &File, CONFIG_FILE_NAME, EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE, 0);
                 if (EFI_ERROR(Status))
                 {
                     Print(L"Error opening config file: %r\n", Status);
                     Root->Close(Root);
                     FreePool(Handles);
                     return Status;
                 }
                 // Read the file content
                 Status = ReadFileContent(File, &Content, &ContentSize);
                 if (EFI_ERROR(Status))
                 {
                     Print(L"Error reading file content: %r\n", Status);
                     File->Close(File);
                     Root->Close(Root);
                     FreePool(Handles);
                     return Status;
                 }
 
                 Print(L"\nFull Config File Content:\n\n%a\n", Content);
                 break;
             case '2':
                 Print(L"\nUpdating Config Values:\n\n");
                 Status = EditConfig(Argc, Argv);
                 if (EFI_ERROR(Status))
                 {
                     Print(L"Error updating config file: %r\n", Status);
                 }
                 else
                 {
                     Print(L"Config file updated successfully.\n");
                 }
                 break;
             case '3':
                 FreePool(Content);
                 File->Close(File);
                 Root->Close(Root);
                 FreePool(Handles);
                 Print(L"Exiting Parser APP.\n");
                 return EFI_SUCCESS;
                 break;
 
             default:
                 Print(L"Invalid option\n");
                 break;
             }
         }
     }
     else if (StrCmp(Argv[1], L"-bsa") == 0)
     {
         return run_bsa_logic(Argc, Argv);
     }
     else if (StrCmp(Argv[1], L"-sct") == 0)
     {
         return run_sct_logic(Argc, Argv);
     }
     else if (StrCmp(Argv[1], L"-sbsa") == 0)
     {
         return run_sbsa_logic(Argc, Argv);
     }
     else if (StrCmp(Argv[1], L"-scrt") == 0)
     {
         return run_scrt_logic(Argc, Argv);
     }
     else if (StrCmp(Argv[1], L"-automation") == 0)
     {
         return run_generic_logic(Argc, Argv);
     }
     else if (StrCmp(Argv[1], L"-bbsr_sct") == 0)
     {
         return run_bbsr_sct_logic(Argc, Argv);
     }
     else
     {
         Print(L"Usage: parser.efi [options]\n");
         Print(L"Options:\n");
         Print(L"  -bsa   Run BSA-specific logic\n");
         Print(L"  -sct   Run SCT-specific logic\n");
         Print(L"  -sbsa  Run SBSA-specific logic\n");
         Print(L"  -scrt   Run SCRT-specific logic\n");
         Print(L"  -bbsr_sct   Run BBSR-SCT logic\n");
         Print(L"  -automation  Run automation-specific logic\n");
     }
 
     return EFI_SUCCESS;
 }
