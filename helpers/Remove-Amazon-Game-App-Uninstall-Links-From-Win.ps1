#Requires -RunAsAdministrator

# Iterate through HKEY_USERS and check for the Uninstall key
$usersKey = Get-ChildItem "Registry::HKEY_USERS"
foreach ($userKey in $usersKey) {
	# Skip the HKEY_USERS key itself
	if ($userKey.PSChildName -ne ".DEFAULT") {
		# Check if the Uninstall key exists under Software\Microsoft\Windows\CurrentVersion
		$path = Join-Path -Path $userKey.PSPath -ChildPath "Software\Microsoft\Windows\CurrentVersion\Uninstall"
		$subkeys = Get-ChildItem -Path $path

		foreach ($subkey in $subkeys) {
			$uninstallString = (Get-ItemProperty -Path $subkey.PSPath).UninstallString
			if ($uninstallString -like "*\\Amazon Game Remover.exe**") {
				$choice = Read-Host "Do you want to delete key $($subkey.PSPath)? (Y/N)"
				if ($choice -eq "Y") {
					Write-Host "Deleting key $($subkey.PSPath)"
					Remove-Item -Path $subkey.PSPath -Force
				}
			}
		}
	}
}

Write-Host "Exiting script in 5 seconds."; Start-Sleep -Seconds 5
exit