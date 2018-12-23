# Trip data sandbox

## ENVIRONMENT

### Creating and loading environments
    **EXPORT:** conda env export > environment.yaml
    **IMPORT:** conda env create -f environment.yaml

## SERVER

### Adjusting TCP Settings for Heavy Load on Windows

    SOURCE: https://docs.oracle.com/cd/E23095_01/Search.93/ATGSearchAdmin/html/s1207adjustingtcpsettingsforheavyload01.html

    The underlying Search architecture that directs searches across multiple
    physical partitions uses TCP/IP ports and non-blocking NIO SocketChannels
    to connect to the Search engines.
    
    These connections remain open in the TIME_WAIT state until the operating
    system times them out. Consequently, under heavy load conditions,
    the available ports on the machine running the Routing module can be exhausted.

    On Windows platforms, the default timeout is 120 seconds, and the maximum number
    of ports is approximately 4,000, resulting in a maximum rate of 33
    connections per second.
    
    If your index has four partitions, each search requires four ports, 
    which provides a maximum query rate of 8.3 queries per second.

    (maximum ports/timeout period)/number of partitions = maximum query rate
    If this rate is exceeded, you may see failures as the supply of TCP/IP ports is exhausted.
    Symptoms include drops in throughput and errors indicating failed network connections.
    
    You can diagnose this problem by observing the system while it is under load,
    using the netstat utility provided on most operating systems.

    To avoid port exhaustion and support high connection rates,
    reduce the TIME_WAIT value and increase the port range.

    To set TcpTimedWaitDelay (TIME_WAIT):
    - Use the regedit command to access the registry subkey:
        HKEY_LOCAL_MACHINE\
        SYSTEM\
        CurrentControlSet\
        Services\
        TCPIP\
        Parameters
    - Create a new REG_DWORD value named TcpTimedWaitDelay.
    - Set the value to 60.
    - Stop and restart the system.

    To set MaxUserPort (ephemeral port range):
    - Use the regedit command to access the registry subkey:
        HKEY_LOCAL_MACHINE\
        SYSTEM\
        CurrentControlSet\
        Services\
        TCPIP\
        Parameters
    - Create a new REG_DWORD value named MaxUserPort.
    - Set this value to 32768.
    - Stop and restart the system.