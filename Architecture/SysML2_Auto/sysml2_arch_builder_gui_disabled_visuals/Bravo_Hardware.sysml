package Bravo_Hardware {
enum def ArchitectureLevel { enum Level1_Domain; enum Level2_ArchitectureElement; }
enum def PortType { enum In; enum Out; enum Bidi; enum Power; enum Ground; enum Analog; }
enum def ConnectionType { enum Net; enum Bus; }
enum def NetReferenceDirection { enum In; enum Out; enum Bidi; }
part def ArchitectureBlock { attribute blockId : ScalarValues::String; }
port def ArchitecturePort { attribute portId : ScalarValues::String; }
connection def ArchitectureConnection { attribute connectionId : ScalarValues::String; }

part def Bravo_Hardware_Architecture {
    part RaspberryPi_5 : ArchitectureBlock {
        attribute blockId = "BLK-0B70BA30C5";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = true;
        attribute color = "#f3e8ff";
        attribute domainColor = "#f3e8ff";
        attribute isHost = true;
    }
    part RF_Transceiver_Array : ArchitectureBlock {
        attribute blockId = "BLK-6BDC725AC3";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#edf7ed";
        attribute domainColor = "#edf7ed";
        attribute isHost = false;
    }
    part Power_Amplifier : ArchitectureBlock {
        attribute blockId = "BLK-D52CEE7D7F";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
    }
    part Beamformer_Array : ArchitectureBlock {
        attribute blockId = "BLK-12884C1B27";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#e8f6f3";
        attribute domainColor = "#e8f6f3";
        attribute isHost = false;
    }
    part Edge_Communication : ArchitectureBlock {
        attribute blockId = "BLK-E5F1CA1EEB";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#e8f6f3";
        attribute domainColor = "#e8f6f3";
        attribute isHost = false;
    }
    part TelemetricsDrone : ArchitectureBlock {
        attribute blockId = "BLK-DCA7060A96";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#edf7ed";
        attribute domainColor = "#edf7ed";
        attribute isHost = false;
    }
    part TelemetricsBarvoMesh : ArchitectureBlock {
        attribute blockId = "BLK-7E925D4EE3";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#e8f6f3";
        attribute domainColor = "#e8f6f3";
        attribute isHost = false;
    }
    part Battery_Management : ArchitectureBlock {
        attribute blockId = "BLK-7072CC0CBD";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#fce4ec";
        attribute domainColor = "#fce4ec";
        attribute isHost = false;
    }
    part PSU_Input : ArchitectureBlock {
        attribute blockId = "BLK-6FE918FE92";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
    }
    part PSU_RaspberryPi_5 : ArchitectureBlock {
        attribute blockId = "BLK-D0D2FB4AD3";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
    }
    part PSU_Power_Amplifier : ArchitectureBlock {
        attribute blockId = "BLK-4EF82E0C73";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
    }
    part PSU_Beamformer_Array : ArchitectureBlock {
        attribute blockId = "BLK-A40D2EDF6C";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
    }
    part PSU_Edge_Com : ArchitectureBlock {
        attribute blockId = "BLK-4A2588ED07";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
    }
    part PSU_Telemetrics : ArchitectureBlock {
        attribute blockId = "BLK-20403C6C49";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
    }
    part Ethernet : ArchitectureBlock {
        attribute blockId = "BLK-FB2509DFF6";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#dae8fc";
        attribute domainColor = "#dae8fc";
        attribute isHost = false;
    }
    part PSU_Ethernet : ArchitectureBlock {
        attribute blockId = "BLK-9660862337";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
    }
}
}
