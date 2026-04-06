using namespace System.IO
using module MyModule

function Get-Data {
    param(
        [string]$Name,
        [int]$Count = 10
    )

    $result = Process-Items -Name $Name -Count $Count
    return $result
}

function Process-Items {
    param(
        [string]$Name,
        [int]$Count
    )

    return @($Name) * $Count
}

class DataProcessor {
    [string]$Name

    DataProcessor([string]$name) {
        $this.Name = $name
    }

    [void] Process() {
        $data = Get-Data -Name $this.Name
    }

    [string] ToString() {
        return $this.Name
    }
}
