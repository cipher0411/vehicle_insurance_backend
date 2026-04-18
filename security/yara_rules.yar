rule Suspicious_PowerShell {
    meta:
        description = "Detects PowerShell commands in files"
        severity = "high"
    strings:
        $ps1 = "powershell" nocase
        $ps2 = "-EncodedCommand" nocase
        $ps3 = "-ExecutionPolicy" nocase
        $ps4 = "Invoke-Expression" nocase
        $ps5 = "IEX" nocase
    condition:
        2 of them
}

rule Malicious_Macro {
    meta:
        description = "Detects malicious Office macros"
        severity = "high"
    strings:
        $m1 = "AutoOpen" nocase
        $m2 = "Workbook_Open" nocase
        $m3 = "Document_Open" nocase
        $m4 = "Shell(" nocase
        $m5 = "CreateObject(\"WScript.Shell\")" nocase
        $m6 = "URLDownloadToFile" nocase
    condition:
        2 of them
}

rule Ransomware_Note {
    meta:
        description = "Detects ransomware notes"
        severity = "critical"
    strings:
        $r1 = "Your files have been encrypted" nocase
        $r2 = "bitcoin" nocase
        $r3 = "decrypt" nocase
        $r4 = "ransom" nocase
        $r5 = ".onion" nocase
    condition:
        2 of them
}

rule Executable_Disguised {
    meta:
        description = "Detects executables disguised as documents"
        severity = "high"
    strings:
        $mz = "MZ"  // DOS header
        $pe = "PE\0\0"  // PE header
    condition:
        $mz at 0 and $pe
}