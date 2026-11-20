package Generic_Architecture {
enum def ArchitectureLevel { enum Level1_Domain; enum Level2_ArchitectureElement; }
enum def PortType { enum In; enum Out; enum Bidi; enum Power; enum Ground; enum Analog; }
enum def ConnectionType { enum Net; enum Bus; }
enum def NetReferenceDirection { enum In; enum Out; enum Bidi; }
part def ArchitectureBlock { attribute blockId : ScalarValues::String; }
port def ArchitecturePort { attribute portId : ScalarValues::String; }
connection def ArchitectureConnection { attribute connectionId : ScalarValues::String; }

part def Generic_Architecture_Architecture {
    part PSU : ArchitectureBlock {
        attribute blockId = "BLK-5D3D5D5154";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        part PSU_SmC : ArchitectureBlock {
            attribute blockId = "BLK-852E3DB2DA";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#f8cecc";
            attribute domainColor = "#f8cecc";
            port UART_Link_1 : ArchitecturePort {
                attribute portId = "PRT-A85E28F3A3";
                attribute portType = "Bidi";
                attribute interfaceName = "UART_Link_1";
                attribute connectionType = "Bus";
                attribute signals = ["UART_Link_1_RX", "UART_Link_1_TX", "UART_Link_1_CTS", "UART_Link_1_RTS"];
                attribute ecadSignals = ["UART_Link_1_RX", "UART_Link_1_TX", "UART_Link_1_CTS", "UART_Link_1_RTS"];
                attribute generatedBy = "BusContentWizard";
                attribute netId = "NET-0EF5AEA09B";
                attribute family = "interface";
                attribute template = "UART_[Link/Port]";
                attribute instanceIndex = "1";
                attribute bcLine = "UART_Link_1 UART_Link_1_RX,UART_Link_1_TX,UART_Link_1_CTS,UART_Link_1_RTS";
                attribute busContentName = "UART_Link_1";
                attribute propagateToParent = false;
            }
            port RES__PSU_INFO_1V8 : ArchitecturePort {
                attribute portId = "PRT-BD8E94A077";
                attribute portType = "In";
                attribute interfaceName = "RES#_PSU_INFO_1V8";
                attribute connectionType = "Net";
                attribute signals = ["RES#_PSU_INFO_1V8"];
                attribute ecadSignals = ["RES#_PSU_INFO_1V8"];
                attribute generatedBy = "BusContentWizard";
                attribute netId = "NET-52AFE7B6D6";
                attribute family = "control";
                attribute template = "RES";
                attribute instanceIndex = "0";
                attribute bcLine = "PSU_Control RES#_PSU_INFO_1V8";
                attribute busContentName = "PSU_Control";
                attribute propagateToParent = false;
            }
        }
    }

    connection UART_Link_1_Reference : ArchitectureConnection {
        attribute connectionId = "REF-373E36F8C1";
        attribute netId = "NET-0EF5AEA09B";
        attribute referenceName = "UART_Link_1";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "UART_Link_1";
        attribute connectionType = "Bus";
        attribute signals = ["UART_Link_1_RX", "UART_Link_1_TX", "UART_Link_1_CTS", "UART_Link_1_RTS"];
        attribute ecadSignals = ["UART_Link_1_RX", "UART_Link_1_TX", "UART_Link_1_CTS", "UART_Link_1_RTS"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-0EF5AEA09B";
        attribute family = "interface";
        attribute template = "UART_[Link/Port]";
        attribute instanceIndex = "1";
        attribute bcLine = "UART_Link_1 UART_Link_1_RX,UART_Link_1_TX,UART_Link_1_CTS,UART_Link_1_RTS";
        attribute busContentName = "UART_Link_1";
        attribute propagateToParent = false;
    }
    connection RES__PSU_INFO_1V8_Reference : ArchitectureConnection {
        attribute connectionId = "REF-2B0E246B0D";
        attribute netId = "NET-52AFE7B6D6";
        attribute referenceName = "RES#_PSU_INFO_1V8";
        attribute referenceDirection = "In";
        attribute interfaceName = "RES#_PSU_INFO_1V8";
        attribute connectionType = "Net";
        attribute signals = ["RES#_PSU_INFO_1V8"];
        attribute ecadSignals = ["RES#_PSU_INFO_1V8"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-52AFE7B6D6";
        attribute family = "control";
        attribute template = "RES";
        attribute instanceIndex = "0";
        attribute bcLine = "PSU_Control RES#_PSU_INFO_1V8";
        attribute busContentName = "PSU_Control";
        attribute propagateToParent = false;
    }
}
}
