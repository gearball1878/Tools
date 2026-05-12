package Spine_Architecture {
enum def ArchitectureLevel { enum Level1_Domain; enum Level2_ArchitectureElement; }
enum def PortType { enum In; enum Out; enum Bidi; enum Power; enum Ground; enum Analog; }
enum def ConnectionType { enum Net; enum Bus; }
enum def NetReferenceDirection { enum In; enum Out; enum Bidi; }
part def ArchitectureBlock { attribute blockId : ScalarValues::String; }
port def ArchitecturePort { attribute portId : ScalarValues::String; }
connection def ArchitectureConnection { attribute connectionId : ScalarValues::String; }

part def Spine_Architecture_Architecture {
    part PSU_JETSON_T5000 : ArchitectureBlock {
        attribute blockId = "BLK-A369FC91BF";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
    }
    part PSU_Audio : ArchitectureBlock {
        attribute blockId = "BLK-1B4A4560E3";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
        port UART_Link_1 : ArchitecturePort {
            attribute portId = "PRT-47297A695B";
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
            attribute propagateToParent = true;
        }
        port UART_Link_2 : ArchitecturePort {
            attribute portId = "PRT-F0C196333A";
            attribute portType = "Bidi";
            attribute interfaceName = "UART_Link_2";
            attribute connectionType = "Bus";
            attribute signals = ["UART_Link_2_RX", "UART_Link_2_TX", "UART_Link_2_CTS", "UART_Link_2_RTS"];
            attribute ecadSignals = ["UART_Link_2_RX", "UART_Link_2_TX", "UART_Link_2_CTS", "UART_Link_2_RTS"];
            attribute generatedBy = "BusContentWizard";
            attribute netId = "NET-5696D142A4";
            attribute family = "interface";
            attribute template = "UART_[Link/Port]";
            attribute instanceIndex = "2";
            attribute bcLine = "UART_Link_2 UART_Link_2_RX,UART_Link_2_TX,UART_Link_2_CTS,UART_Link_2_RTS";
            attribute busContentName = "UART_Link_2";
            attribute propagateToParent = true;
        }
    }
    part PSU_Video : ArchitectureBlock {
        attribute blockId = "BLK-B824BCF6E7";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
        part PSU_Video_DESER : ArchitectureBlock {
            attribute blockId = "BLK-CB93ACA81C";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#f8cecc";
            attribute domainColor = "#f8cecc";
        }
    }
    part PSU_Radar : ArchitectureBlock {
        attribute blockId = "BLK-7112D97B34";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
    }
    part PSU_PMU_Micro : ArchitectureBlock {
        attribute blockId = "BLK-746960DE6D";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
    }
    part PSU_Ethernet : ArchitectureBlock {
        attribute blockId = "BLK-8890E085E1";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
        part PSU_ETH_Switch : ArchitectureBlock {
            attribute blockId = "BLK-2BDBE31CB7";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#f8cecc";
            attribute domainColor = "#f8cecc";
            port ETH_SGMII_Link_1 : ArchitecturePort {
                attribute portId = "PRT-1B98E75187";
                attribute portType = "Bidi";
                attribute interfaceName = "ETH_SGMII_Link_1";
                attribute connectionType = "Bus";
                attribute signals = ["ETH_SGMII_Link_1_TXD_P", "ETH_SGMII_Link_1_TXD_N", "ETH_SGMII_Link_1_RXD_P", "ETH_SGMII_Link_1_RXD_N"];
                attribute ecadSignals = ["ETH_SGMII_Link_1_TXD_P", "ETH_SGMII_Link_1_TXD_N", "ETH_SGMII_Link_1_RXD_P", "ETH_SGMII_Link_1_RXD_N"];
                attribute generatedBy = "BusContentWizard";
                attribute netId = "NET-8EF8E93549";
                attribute family = "interface";
                attribute template = "ETH_SGMII_[Link/Port]";
                attribute instanceIndex = "1";
                attribute bcLine = "ETH_SGMII_Link_1 ETH_SGMII_Link_1_TXD_P,ETH_SGMII_Link_1_TXD_N,ETH_SGMII_Link_1_RXD_P,ETH_SGMII_Link_1_RXD_N";
                attribute busContentName = "ETH_SGMII_Link_1";
                attribute copiedFrom = "JETSON_T5000.ETH_SGMII_Link_1";
            }
        }
        part PSU_ETH_PHY_FIBRE : ArchitectureBlock {
            attribute blockId = "BLK-D72BBA7D2C";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#f8cecc";
            attribute domainColor = "#f8cecc";
        }
        part PSU_ETH_10GBASE_T_PHY : ArchitectureBlock {
            attribute blockId = "BLK-D273D01C43";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#f8cecc";
            attribute domainColor = "#f8cecc";
        }
    }
    part PSU_Input : ArchitectureBlock {
        attribute blockId = "BLK-5B5CB5534D";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        attribute isHost = false;
        port VBAT_PSU_IN_230V : ArchitecturePort {
            attribute portId = "PRT-33C1C68FD8";
            attribute portType = "Power";
            attribute interfaceName = "VBAT_PSU_IN_230V";
            attribute connectionType = "Net";
            attribute signals = ["VBAT_PSU_IN_230V"];
            attribute ecadSignals = ["VBAT_PSU_IN_230V"];
            attribute generatedBy = "BusContentWizard";
            attribute netId = "NET-1A704E69DE";
            attribute family = "power";
            attribute template = "VBAT";
            attribute instanceIndex = "0";
            attribute bcLine = "Power_Signals VBAT_PSU_IN_230V";
            attribute busContentName = "Power_Signals";
            attribute powerDirection = "PowerIn";
        }
        port VBAT_PSU_IN_24V : ArchitecturePort {
            attribute portId = "PRT-CD659493B0";
            attribute portType = "Power";
            attribute interfaceName = "VBAT_PSU_IN_24V";
            attribute connectionType = "Net";
            attribute signals = ["VBAT_PSU_IN_24V"];
            attribute ecadSignals = ["VBAT_PSU_IN_24V"];
            attribute generatedBy = "BusContentWizard";
            attribute netId = "NET-F5F89AE832";
            attribute family = "power";
            attribute template = "VBAT";
            attribute instanceIndex = "0";
            attribute bcLine = "Power_Signals VBAT_PSU_IN_24V";
            attribute busContentName = "Power_Signals";
            attribute powerDirection = "PowerIn";
        }
        port VBAT_PSU_BOARD_24V : ArchitecturePort {
            attribute portId = "PRT-09BAFE284E";
            attribute portType = "Power";
            attribute interfaceName = "VBAT_PSU_BOARD_24V";
            attribute connectionType = "Net";
            attribute signals = ["VBAT_PSU_BOARD_24V"];
            attribute ecadSignals = ["VBAT_PSU_BOARD_24V"];
            attribute generatedBy = "BusContentWizard";
            attribute netId = "NET-706E6FBB03";
            attribute family = "power";
            attribute template = "VBAT";
            attribute instanceIndex = "0";
            attribute bcLine = "Power_Signals VBAT_PSU_BOARD_24V";
            attribute busContentName = "Power_Signals";
            attribute powerDirection = "PowerOut";
        }
    }
    part Edge_Connectors : ArchitectureBlock {
        attribute blockId = "BLK-62C72179D3";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#e8f6f3";
        attribute domainColor = "#e8f6f3";
        attribute isHost = false;
    }
    part JETSON_T5000 : ArchitectureBlock {
        attribute blockId = "BLK-3E75E1E6F6";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = true;
        attribute color = "#f3e8ff";
        attribute domainColor = "#f3e8ff";
        attribute isHost = true;
        port CSI2_Link_1 : ArchitecturePort {
            attribute portId = "PRT-F8B6DA1754";
            attribute portType = "Bidi";
            attribute interfaceName = "CSI2_Link_1";
            attribute connectionType = "Bus";
            attribute signals = ["CSI2_Link_1_Trio_1_A_D0_P", "CSI2_Link_1_Trio_1_B_D0_N", "CSI2_Link_1_Trio_2_B_D1_P", "CSI2_Link_1_Trio_2_C_D1_N", "CSI2_Link_1_Trio_3_A_D2_P", "CSI2_Link_1_Trio_3_B_D2_N", "CSI2_Link_1_Trio_4_B_D3_P", "CSI2_Link_1_Trio_4_C_D3_N", "CSI2_Link_1_Trio_3_C_CLK1_P", "CSI2_Link_1_Trio_4_A_CLK1_N", "CSI2_Link_1_Trio_1_C_CLK2_P", "CSI2_Link_1_Trio_2_A_CLK2_N"];
            attribute ecadSignals = ["CSI2_Link_1_Trio_1_A_D0_P", "CSI2_Link_1_Trio_1_B_D0_N", "CSI2_Link_1_Trio_2_B_D1_P", "CSI2_Link_1_Trio_2_C_D1_N", "CSI2_Link_1_Trio_3_A_D2_P", "CSI2_Link_1_Trio_3_B_D2_N", "CSI2_Link_1_Trio_4_B_D3_P", "CSI2_Link_1_Trio_4_C_D3_N", "CSI2_Link_1_Trio_3_C_CLK1_P", "CSI2_Link_1_Trio_4_A_CLK1_N", "CSI2_Link_1_Trio_1_C_CLK2_P", "CSI2_Link_1_Trio_2_A_CLK2_N"];
            attribute generatedBy = "BusContentWizard";
            attribute netId = "NET-187341D3D0";
            attribute family = "interface";
            attribute template = "CSI2_[Link/Port]";
            attribute instanceIndex = "1";
            attribute bcLine = "CSI2_Link_1 CSI2_Link_1_Trio_1_A_D0_P,CSI2_Link_1_Trio_1_B_D0_N,CSI2_Link_1_Trio_2_B_D1_P,CSI2_Link_1_Trio_2_C_D1_N,CSI2_Link_1_Trio_3_A_D2_P,CSI2_Link_1_Trio_3_B_D2_N,CSI2_Link_1_Trio_4_B_D3_P,CSI2_Link_1_Trio_4_C_D3_N,CSI2_Link_1_Trio_3_C_CLK1_P,CSI2_Link_1_Trio_4_A_CLK1_N,CSI2_Link_1_Trio_1_C_CLK2_P,CSI2_Link_1_Trio_2_A_CLK2_N";
            attribute busContentName = "CSI2_Link_1";
        }
        port CSI2_Link_2 : ArchitecturePort {
            attribute portId = "PRT-381A010B94";
            attribute portType = "Bidi";
            attribute interfaceName = "CSI2_Link_2";
            attribute connectionType = "Bus";
            attribute signals = ["CSI2_Link_2_Trio_1_A_D0_P", "CSI2_Link_2_Trio_1_B_D0_N", "CSI2_Link_2_Trio_2_B_D1_P", "CSI2_Link_2_Trio_2_C_D1_N", "CSI2_Link_2_Trio_3_A_D2_P", "CSI2_Link_2_Trio_3_B_D2_N", "CSI2_Link_2_Trio_4_B_D3_P", "CSI2_Link_2_Trio_4_C_D3_N", "CSI2_Link_2_Trio_3_C_CLK1_P", "CSI2_Link_2_Trio_4_A_CLK1_N", "CSI2_Link_2_Trio_1_C_CLK2_P", "CSI2_Link_2_Trio_2_A_CLK2_N"];
            attribute ecadSignals = ["CSI2_Link_2_Trio_1_A_D0_P", "CSI2_Link_2_Trio_1_B_D0_N", "CSI2_Link_2_Trio_2_B_D1_P", "CSI2_Link_2_Trio_2_C_D1_N", "CSI2_Link_2_Trio_3_A_D2_P", "CSI2_Link_2_Trio_3_B_D2_N", "CSI2_Link_2_Trio_4_B_D3_P", "CSI2_Link_2_Trio_4_C_D3_N", "CSI2_Link_2_Trio_3_C_CLK1_P", "CSI2_Link_2_Trio_4_A_CLK1_N", "CSI2_Link_2_Trio_1_C_CLK2_P", "CSI2_Link_2_Trio_2_A_CLK2_N"];
            attribute generatedBy = "BusContentWizard";
            attribute netId = "NET-D0688FFAAF";
            attribute family = "interface";
            attribute template = "CSI2_[Link/Port]";
            attribute instanceIndex = "2";
            attribute bcLine = "CSI2_Link_2 CSI2_Link_2_Trio_1_A_D0_P,CSI2_Link_2_Trio_1_B_D0_N,CSI2_Link_2_Trio_2_B_D1_P,CSI2_Link_2_Trio_2_C_D1_N,CSI2_Link_2_Trio_3_A_D2_P,CSI2_Link_2_Trio_3_B_D2_N,CSI2_Link_2_Trio_4_B_D3_P,CSI2_Link_2_Trio_4_C_D3_N,CSI2_Link_2_Trio_3_C_CLK1_P,CSI2_Link_2_Trio_4_A_CLK1_N,CSI2_Link_2_Trio_1_C_CLK2_P,CSI2_Link_2_Trio_2_A_CLK2_N";
            attribute busContentName = "CSI2_Link_2";
        }
        port CSI2_Link_3 : ArchitecturePort {
            attribute portId = "PRT-D53A276F58";
            attribute portType = "Bidi";
            attribute interfaceName = "CSI2_Link_3";
            attribute connectionType = "Bus";
            attribute signals = ["CSI2_Link_3_Trio_1_A_D0_P", "CSI2_Link_3_Trio_1_B_D0_N", "CSI2_Link_3_Trio_2_B_D1_P", "CSI2_Link_3_Trio_2_C_D1_N", "CSI2_Link_3_Trio_3_A_D2_P", "CSI2_Link_3_Trio_3_B_D2_N", "CSI2_Link_3_Trio_4_B_D3_P", "CSI2_Link_3_Trio_4_C_D3_N", "CSI2_Link_3_Trio_3_C_CLK1_P", "CSI2_Link_3_Trio_4_A_CLK1_N", "CSI2_Link_3_Trio_1_C_CLK2_P", "CSI2_Link_3_Trio_2_A_CLK2_N"];
            attribute ecadSignals = ["CSI2_Link_3_Trio_1_A_D0_P", "CSI2_Link_3_Trio_1_B_D0_N", "CSI2_Link_3_Trio_2_B_D1_P", "CSI2_Link_3_Trio_2_C_D1_N", "CSI2_Link_3_Trio_3_A_D2_P", "CSI2_Link_3_Trio_3_B_D2_N", "CSI2_Link_3_Trio_4_B_D3_P", "CSI2_Link_3_Trio_4_C_D3_N", "CSI2_Link_3_Trio_3_C_CLK1_P", "CSI2_Link_3_Trio_4_A_CLK1_N", "CSI2_Link_3_Trio_1_C_CLK2_P", "CSI2_Link_3_Trio_2_A_CLK2_N"];
            attribute generatedBy = "BusContentWizard";
            attribute netId = "NET-1DB177E4F8";
            attribute family = "interface";
            attribute template = "CSI2_[Link/Port]";
            attribute instanceIndex = "3";
            attribute bcLine = "CSI2_Link_3 CSI2_Link_3_Trio_1_A_D0_P,CSI2_Link_3_Trio_1_B_D0_N,CSI2_Link_3_Trio_2_B_D1_P,CSI2_Link_3_Trio_2_C_D1_N,CSI2_Link_3_Trio_3_A_D2_P,CSI2_Link_3_Trio_3_B_D2_N,CSI2_Link_3_Trio_4_B_D3_P,CSI2_Link_3_Trio_4_C_D3_N,CSI2_Link_3_Trio_3_C_CLK1_P,CSI2_Link_3_Trio_4_A_CLK1_N,CSI2_Link_3_Trio_1_C_CLK2_P,CSI2_Link_3_Trio_2_A_CLK2_N";
            attribute busContentName = "CSI2_Link_3";
        }
        port ETH_SGMII_Link_1 : ArchitecturePort {
            attribute portId = "PRT-6940CEBC7C";
            attribute portType = "Bidi";
            attribute interfaceName = "ETH_SGMII_Link_1";
            attribute connectionType = "Bus";
            attribute signals = ["ETH_SGMII_Link_1_TXD_P", "ETH_SGMII_Link_1_TXD_N", "ETH_SGMII_Link_1_RXD_P", "ETH_SGMII_Link_1_RXD_N"];
            attribute ecadSignals = ["ETH_SGMII_Link_1_TXD_P", "ETH_SGMII_Link_1_TXD_N", "ETH_SGMII_Link_1_RXD_P", "ETH_SGMII_Link_1_RXD_N"];
            attribute generatedBy = "BusContentWizard";
            attribute netId = "NET-8EF8E93549";
            attribute family = "interface";
            attribute template = "ETH_SGMII_[Link/Port]";
            attribute instanceIndex = "1";
            attribute bcLine = "ETH_SGMII_Link_1 ETH_SGMII_Link_1_TXD_P,ETH_SGMII_Link_1_TXD_N,ETH_SGMII_Link_1_RXD_P,ETH_SGMII_Link_1_RXD_N";
            attribute busContentName = "ETH_SGMII_Link_1";
        }
    }
    part Audio : ArchitectureBlock {
        attribute blockId = "BLK-0B7D74F99A";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f5f5f5";
        attribute domainColor = "#f5f5f5";
        attribute isHost = false;
        part Microphone_Array : ArchitectureBlock {
            attribute blockId = "BLK-EF74087E19";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#f5f5f5";
            attribute domainColor = "#f5f5f5";
        }
    }
    part Video : ArchitectureBlock {
        attribute blockId = "BLK-6AB5223C98";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#fff2cc";
        attribute domainColor = "#fff2cc";
        attribute isHost = false;
        part GMSL_DESER_1 : ArchitectureBlock {
            attribute blockId = "BLK-B9E5AE8B8C";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#fff2cc";
            attribute domainColor = "#fff2cc";
            port CSI2_Link_1 : ArchitecturePort {
                attribute portId = "PRT-9DC30BBB34";
                attribute portType = "Bidi";
                attribute interfaceName = "CSI2_Link_1";
                attribute connectionType = "Bus";
                attribute signals = ["CSI2_Link_1_Trio_1_A_D0_P", "CSI2_Link_1_Trio_1_B_D0_N", "CSI2_Link_1_Trio_2_B_D1_P", "CSI2_Link_1_Trio_2_C_D1_N", "CSI2_Link_1_Trio_3_A_D2_P", "CSI2_Link_1_Trio_3_B_D2_N", "CSI2_Link_1_Trio_4_B_D3_P", "CSI2_Link_1_Trio_4_C_D3_N", "CSI2_Link_1_Trio_3_C_CLK1_P", "CSI2_Link_1_Trio_4_A_CLK1_N", "CSI2_Link_1_Trio_1_C_CLK2_P", "CSI2_Link_1_Trio_2_A_CLK2_N"];
                attribute ecadSignals = ["CSI2_Link_1_Trio_1_A_D0_P", "CSI2_Link_1_Trio_1_B_D0_N", "CSI2_Link_1_Trio_2_B_D1_P", "CSI2_Link_1_Trio_2_C_D1_N", "CSI2_Link_1_Trio_3_A_D2_P", "CSI2_Link_1_Trio_3_B_D2_N", "CSI2_Link_1_Trio_4_B_D3_P", "CSI2_Link_1_Trio_4_C_D3_N", "CSI2_Link_1_Trio_3_C_CLK1_P", "CSI2_Link_1_Trio_4_A_CLK1_N", "CSI2_Link_1_Trio_1_C_CLK2_P", "CSI2_Link_1_Trio_2_A_CLK2_N"];
                attribute generatedBy = "BusContentWizard";
                attribute netId = "NET-187341D3D0";
                attribute family = "interface";
                attribute template = "CSI2_[Link/Port]";
                attribute instanceIndex = "1";
                attribute bcLine = "CSI2_Link_1 CSI2_Link_1_Trio_1_A_D0_P,CSI2_Link_1_Trio_1_B_D0_N,CSI2_Link_1_Trio_2_B_D1_P,CSI2_Link_1_Trio_2_C_D1_N,CSI2_Link_1_Trio_3_A_D2_P,CSI2_Link_1_Trio_3_B_D2_N,CSI2_Link_1_Trio_4_B_D3_P,CSI2_Link_1_Trio_4_C_D3_N,CSI2_Link_1_Trio_3_C_CLK1_P,CSI2_Link_1_Trio_4_A_CLK1_N,CSI2_Link_1_Trio_1_C_CLK2_P,CSI2_Link_1_Trio_2_A_CLK2_N";
                attribute busContentName = "CSI2_Link_1";
                attribute copiedFrom = "JETSON_T5000.CSI2_Link_1";
            }
        }
        part GMSL_DESER_2 : ArchitectureBlock {
            attribute blockId = "BLK-C0C8BEF10D";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#fff2cc";
            attribute domainColor = "#fff2cc";
            port CSI2_Link_2 : ArchitecturePort {
                attribute portId = "PRT-BF49423111";
                attribute portType = "Bidi";
                attribute interfaceName = "CSI2_Link_2";
                attribute connectionType = "Bus";
                attribute signals = ["CSI2_Link_2_Trio_1_A_D0_P", "CSI2_Link_2_Trio_1_B_D0_N", "CSI2_Link_2_Trio_2_B_D1_P", "CSI2_Link_2_Trio_2_C_D1_N", "CSI2_Link_2_Trio_3_A_D2_P", "CSI2_Link_2_Trio_3_B_D2_N", "CSI2_Link_2_Trio_4_B_D3_P", "CSI2_Link_2_Trio_4_C_D3_N", "CSI2_Link_2_Trio_3_C_CLK1_P", "CSI2_Link_2_Trio_4_A_CLK1_N", "CSI2_Link_2_Trio_1_C_CLK2_P", "CSI2_Link_2_Trio_2_A_CLK2_N"];
                attribute ecadSignals = ["CSI2_Link_2_Trio_1_A_D0_P", "CSI2_Link_2_Trio_1_B_D0_N", "CSI2_Link_2_Trio_2_B_D1_P", "CSI2_Link_2_Trio_2_C_D1_N", "CSI2_Link_2_Trio_3_A_D2_P", "CSI2_Link_2_Trio_3_B_D2_N", "CSI2_Link_2_Trio_4_B_D3_P", "CSI2_Link_2_Trio_4_C_D3_N", "CSI2_Link_2_Trio_3_C_CLK1_P", "CSI2_Link_2_Trio_4_A_CLK1_N", "CSI2_Link_2_Trio_1_C_CLK2_P", "CSI2_Link_2_Trio_2_A_CLK2_N"];
                attribute generatedBy = "BusContentWizard";
                attribute netId = "NET-D0688FFAAF";
                attribute family = "interface";
                attribute template = "CSI2_[Link/Port]";
                attribute instanceIndex = "2";
                attribute bcLine = "CSI2_Link_2 CSI2_Link_2_Trio_1_A_D0_P,CSI2_Link_2_Trio_1_B_D0_N,CSI2_Link_2_Trio_2_B_D1_P,CSI2_Link_2_Trio_2_C_D1_N,CSI2_Link_2_Trio_3_A_D2_P,CSI2_Link_2_Trio_3_B_D2_N,CSI2_Link_2_Trio_4_B_D3_P,CSI2_Link_2_Trio_4_C_D3_N,CSI2_Link_2_Trio_3_C_CLK1_P,CSI2_Link_2_Trio_4_A_CLK1_N,CSI2_Link_2_Trio_1_C_CLK2_P,CSI2_Link_2_Trio_2_A_CLK2_N";
                attribute busContentName = "CSI2_Link_2";
                attribute copiedFrom = "JETSON_T5000.CSI2_Link_2";
            }
        }
        part GMSL_DESER_3 : ArchitectureBlock {
            attribute blockId = "BLK-A439040255";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#fff2cc";
            attribute domainColor = "#fff2cc";
            port CSI2_Link_3 : ArchitecturePort {
                attribute portId = "PRT-3ED32F606B";
                attribute portType = "Bidi";
                attribute interfaceName = "CSI2_Link_3";
                attribute connectionType = "Bus";
                attribute signals = ["CSI2_Link_3_Trio_1_A_D0_P", "CSI2_Link_3_Trio_1_B_D0_N", "CSI2_Link_3_Trio_2_B_D1_P", "CSI2_Link_3_Trio_2_C_D1_N", "CSI2_Link_3_Trio_3_A_D2_P", "CSI2_Link_3_Trio_3_B_D2_N", "CSI2_Link_3_Trio_4_B_D3_P", "CSI2_Link_3_Trio_4_C_D3_N", "CSI2_Link_3_Trio_3_C_CLK1_P", "CSI2_Link_3_Trio_4_A_CLK1_N", "CSI2_Link_3_Trio_1_C_CLK2_P", "CSI2_Link_3_Trio_2_A_CLK2_N"];
                attribute ecadSignals = ["CSI2_Link_3_Trio_1_A_D0_P", "CSI2_Link_3_Trio_1_B_D0_N", "CSI2_Link_3_Trio_2_B_D1_P", "CSI2_Link_3_Trio_2_C_D1_N", "CSI2_Link_3_Trio_3_A_D2_P", "CSI2_Link_3_Trio_3_B_D2_N", "CSI2_Link_3_Trio_4_B_D3_P", "CSI2_Link_3_Trio_4_C_D3_N", "CSI2_Link_3_Trio_3_C_CLK1_P", "CSI2_Link_3_Trio_4_A_CLK1_N", "CSI2_Link_3_Trio_1_C_CLK2_P", "CSI2_Link_3_Trio_2_A_CLK2_N"];
                attribute generatedBy = "BusContentWizard";
                attribute netId = "NET-1DB177E4F8";
                attribute family = "interface";
                attribute template = "CSI2_[Link/Port]";
                attribute instanceIndex = "3";
                attribute bcLine = "CSI2_Link_3 CSI2_Link_3_Trio_1_A_D0_P,CSI2_Link_3_Trio_1_B_D0_N,CSI2_Link_3_Trio_2_B_D1_P,CSI2_Link_3_Trio_2_C_D1_N,CSI2_Link_3_Trio_3_A_D2_P,CSI2_Link_3_Trio_3_B_D2_N,CSI2_Link_3_Trio_4_B_D3_P,CSI2_Link_3_Trio_4_C_D3_N,CSI2_Link_3_Trio_3_C_CLK1_P,CSI2_Link_3_Trio_4_A_CLK1_N,CSI2_Link_3_Trio_1_C_CLK2_P,CSI2_Link_3_Trio_2_A_CLK2_N";
                attribute busContentName = "CSI2_Link_3";
                attribute copiedFrom = "JETSON_T5000.CSI2_Link_3";
            }
        }
        part PTZ_STEPPERS : ArchitectureBlock {
            attribute blockId = "BLK-B2ABE22D0D";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#fff2cc";
            attribute domainColor = "#fff2cc";
        }
    }
    part Radar : ArchitectureBlock {
        attribute blockId = "BLK-16FEA19361";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#ffe6cc";
        attribute domainColor = "#ffe6cc";
        attribute isHost = false;
    }
    part PMU_Micro : ArchitectureBlock {
        attribute blockId = "BLK-C021848BAA";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#e1d5e7";
        attribute domainColor = "#e1d5e7";
        attribute isHost = false;
        part PMU_MCU : ArchitectureBlock {
            attribute blockId = "BLK-53FC3AC7DC";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#e1d5e7";
            attribute domainColor = "#e1d5e7";
        }
    }
    part Ethernet : ArchitectureBlock {
        attribute blockId = "BLK-E7DBEB4C5E";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#dae8fc";
        attribute domainColor = "#dae8fc";
        attribute isHost = false;
        part ETH_Switch_1 : ArchitectureBlock {
            attribute blockId = "BLK-624D405B75";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = true;
            attribute color = "#dae8fc";
            attribute domainColor = "#dae8fc";
            attribute isHost = true;
            port ETH_10G_MII_Link_1 : ArchitecturePort {
                attribute portId = "PRT-35F4752DAC";
                attribute portType = "Bidi";
                attribute interfaceName = "ETH_10G_MII_Link_1";
                attribute connectionType = "Bus";
                attribute signals = ["ETH_10G_MII_Link_1_TX_P", "ETH_10G_MII_Link_1_TX_N", "ETH_10G_MII_Link_1_RX_P", "ETH_10G_MII_Link_1_RX_N"];
                attribute ecadSignals = ["ETH_10G_MII_Link_1_TX_P", "ETH_10G_MII_Link_1_TX_N", "ETH_10G_MII_Link_1_RX_P", "ETH_10G_MII_Link_1_RX_N"];
                attribute generatedBy = "BusContentWizard";
                attribute netId = "NET-2C590E7B87";
                attribute family = "interface";
                attribute template = "ETH_10G_MII_[Link/Port]";
                attribute instanceIndex = "1";
                attribute bcLine = "ETH_10G_MII_Link_1 ETH_10G_MII_Link_1_TX_P,ETH_10G_MII_Link_1_TX_N,ETH_10G_MII_Link_1_RX_P,ETH_10G_MII_Link_1_RX_N";
                attribute busContentName = "ETH_10G_MII_Link_1";
            }
            port ETH_10G_MII_Link_2 : ArchitecturePort {
                attribute portId = "PRT-73264A5804";
                attribute portType = "Bidi";
                attribute interfaceName = "ETH_10G_MII_Link_2";
                attribute connectionType = "Bus";
                attribute signals = ["ETH_10G_MII_Link_2_TX_P", "ETH_10G_MII_Link_2_TX_N", "ETH_10G_MII_Link_2_RX_P", "ETH_10G_MII_Link_2_RX_N"];
                attribute ecadSignals = ["ETH_10G_MII_Link_2_TX_P", "ETH_10G_MII_Link_2_TX_N", "ETH_10G_MII_Link_2_RX_P", "ETH_10G_MII_Link_2_RX_N"];
                attribute generatedBy = "BusContentWizard";
                attribute netId = "NET-A3170EDE26";
                attribute family = "interface";
                attribute template = "ETH_10G_MII_[Link/Port]";
                attribute instanceIndex = "2";
                attribute bcLine = "ETH_10G_MII_Link_2 ETH_10G_MII_Link_2_TX_P,ETH_10G_MII_Link_2_TX_N,ETH_10G_MII_Link_2_RX_P,ETH_10G_MII_Link_2_RX_N";
                attribute busContentName = "ETH_10G_MII_Link_2";
            }
            port ETH_10G_MII_Link_3 : ArchitecturePort {
                attribute portId = "PRT-E5ADD71BD5";
                attribute portType = "Bidi";
                attribute interfaceName = "ETH_10G_MII_Link_3";
                attribute connectionType = "Bus";
                attribute signals = ["ETH_10G_MII_Link_3_TX_P", "ETH_10G_MII_Link_3_TX_N", "ETH_10G_MII_Link_3_RX_P", "ETH_10G_MII_Link_3_RX_N"];
                attribute ecadSignals = ["ETH_10G_MII_Link_3_TX_P", "ETH_10G_MII_Link_3_TX_N", "ETH_10G_MII_Link_3_RX_P", "ETH_10G_MII_Link_3_RX_N"];
                attribute generatedBy = "BusContentWizard";
                attribute netId = "NET-ED2317EE8E";
                attribute family = "interface";
                attribute template = "ETH_10G_MII_[Link/Port]";
                attribute instanceIndex = "3";
                attribute bcLine = "ETH_10G_MII_Link_3 ETH_10G_MII_Link_3_TX_P,ETH_10G_MII_Link_3_TX_N,ETH_10G_MII_Link_3_RX_P,ETH_10G_MII_Link_3_RX_N";
                attribute busContentName = "ETH_10G_MII_Link_3";
            }
            port ETH_10G_MII_Link_4 : ArchitecturePort {
                attribute portId = "PRT-1F96FB16BB";
                attribute portType = "Bidi";
                attribute interfaceName = "ETH_10G_MII_Link_4";
                attribute connectionType = "Bus";
                attribute signals = ["ETH_10G_MII_Link_4_TX_P", "ETH_10G_MII_Link_4_TX_N", "ETH_10G_MII_Link_4_RX_P", "ETH_10G_MII_Link_4_RX_N"];
                attribute ecadSignals = ["ETH_10G_MII_Link_4_TX_P", "ETH_10G_MII_Link_4_TX_N", "ETH_10G_MII_Link_4_RX_P", "ETH_10G_MII_Link_4_RX_N"];
                attribute generatedBy = "BusContentWizard";
                attribute netId = "NET-C5406E7CB0";
                attribute family = "interface";
                attribute template = "ETH_10G_MII_[Link/Port]";
                attribute instanceIndex = "4";
                attribute bcLine = "ETH_10G_MII_Link_4 ETH_10G_MII_Link_4_TX_P,ETH_10G_MII_Link_4_TX_N,ETH_10G_MII_Link_4_RX_P,ETH_10G_MII_Link_4_RX_N";
                attribute busContentName = "ETH_10G_MII_Link_4";
            }
            port ETH_10G_MII_Link_5 : ArchitecturePort {
                attribute portId = "PRT-21C793B0A3";
                attribute portType = "Bidi";
                attribute interfaceName = "ETH_10G_MII_Link_5";
                attribute connectionType = "Bus";
                attribute signals = ["ETH_10G_MII_Link_5_TX_P", "ETH_10G_MII_Link_5_TX_N", "ETH_10G_MII_Link_5_RX_P", "ETH_10G_MII_Link_5_RX_N"];
                attribute ecadSignals = ["ETH_10G_MII_Link_5_TX_P", "ETH_10G_MII_Link_5_TX_N", "ETH_10G_MII_Link_5_RX_P", "ETH_10G_MII_Link_5_RX_N"];
                attribute generatedBy = "BusContentWizard";
                attribute netId = "NET-E6F4417864";
                attribute family = "interface";
                attribute template = "ETH_10G_MII_[Link/Port]";
                attribute instanceIndex = "5";
                attribute bcLine = "ETH_10G_MII_Link_5 ETH_10G_MII_Link_5_TX_P,ETH_10G_MII_Link_5_TX_N,ETH_10G_MII_Link_5_RX_P,ETH_10G_MII_Link_5_RX_N";
                attribute busContentName = "ETH_10G_MII_Link_5";
            }
        }
        part ETH_10G_PHY_FIBRE_1 : ArchitectureBlock {
            attribute blockId = "BLK-217E0897A0";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#dae8fc";
            attribute domainColor = "#dae8fc";
            attribute isHost = false;
        }
        part ETH_10G_PHY_FIBRE_2 : ArchitectureBlock {
            attribute blockId = "BLK-EFE99D4D7D";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#dae8fc";
            attribute domainColor = "#dae8fc";
            attribute isHost = false;
        }
        part ETH_10GBASE_T_PHY_1 : ArchitectureBlock {
            attribute blockId = "BLK-04C585BC03";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#dae8fc";
            attribute domainColor = "#dae8fc";
            attribute isHost = false;
        }
        part ETH_10GBASE_T_PHY_2 : ArchitectureBlock {
            attribute blockId = "BLK-D6E228CF02";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#dae8fc";
            attribute domainColor = "#dae8fc";
            attribute isHost = false;
        }
    }

    connection CSI2_Link_1_Reference : ArchitectureConnection {
        attribute connectionId = "REF-1A7DA9B74F";
        attribute netId = "NET-187341D3D0";
        attribute referenceName = "CSI2_Link_1";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "CSI2_Link_1";
        attribute connectionType = "Bus";
        attribute signals = ["CSI2_Link_1_Trio_1_A_D0_P", "CSI2_Link_1_Trio_1_B_D0_N", "CSI2_Link_1_Trio_2_B_D1_P", "CSI2_Link_1_Trio_2_C_D1_N", "CSI2_Link_1_Trio_3_A_D2_P", "CSI2_Link_1_Trio_3_B_D2_N", "CSI2_Link_1_Trio_4_B_D3_P", "CSI2_Link_1_Trio_4_C_D3_N", "CSI2_Link_1_Trio_3_C_CLK1_P", "CSI2_Link_1_Trio_4_A_CLK1_N", "CSI2_Link_1_Trio_1_C_CLK2_P", "CSI2_Link_1_Trio_2_A_CLK2_N"];
        attribute ecadSignals = ["CSI2_Link_1_Trio_1_A_D0_P", "CSI2_Link_1_Trio_1_B_D0_N", "CSI2_Link_1_Trio_2_B_D1_P", "CSI2_Link_1_Trio_2_C_D1_N", "CSI2_Link_1_Trio_3_A_D2_P", "CSI2_Link_1_Trio_3_B_D2_N", "CSI2_Link_1_Trio_4_B_D3_P", "CSI2_Link_1_Trio_4_C_D3_N", "CSI2_Link_1_Trio_3_C_CLK1_P", "CSI2_Link_1_Trio_4_A_CLK1_N", "CSI2_Link_1_Trio_1_C_CLK2_P", "CSI2_Link_1_Trio_2_A_CLK2_N"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-187341D3D0";
        attribute family = "interface";
        attribute template = "CSI2_[Link/Port]";
        attribute instanceIndex = "1";
        attribute bcLine = "CSI2_Link_1 CSI2_Link_1_Trio_1_A_D0_P,CSI2_Link_1_Trio_1_B_D0_N,CSI2_Link_1_Trio_2_B_D1_P,CSI2_Link_1_Trio_2_C_D1_N,CSI2_Link_1_Trio_3_A_D2_P,CSI2_Link_1_Trio_3_B_D2_N,CSI2_Link_1_Trio_4_B_D3_P,CSI2_Link_1_Trio_4_C_D3_N,CSI2_Link_1_Trio_3_C_CLK1_P,CSI2_Link_1_Trio_4_A_CLK1_N,CSI2_Link_1_Trio_1_C_CLK2_P,CSI2_Link_1_Trio_2_A_CLK2_N";
        attribute busContentName = "CSI2_Link_1";
    }
    connection CSI2_Link_2_Reference : ArchitectureConnection {
        attribute connectionId = "REF-059FB5BCEA";
        attribute netId = "NET-D0688FFAAF";
        attribute referenceName = "CSI2_Link_2";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "CSI2_Link_2";
        attribute connectionType = "Bus";
        attribute signals = ["CSI2_Link_2_Trio_1_A_D0_P", "CSI2_Link_2_Trio_1_B_D0_N", "CSI2_Link_2_Trio_2_B_D1_P", "CSI2_Link_2_Trio_2_C_D1_N", "CSI2_Link_2_Trio_3_A_D2_P", "CSI2_Link_2_Trio_3_B_D2_N", "CSI2_Link_2_Trio_4_B_D3_P", "CSI2_Link_2_Trio_4_C_D3_N", "CSI2_Link_2_Trio_3_C_CLK1_P", "CSI2_Link_2_Trio_4_A_CLK1_N", "CSI2_Link_2_Trio_1_C_CLK2_P", "CSI2_Link_2_Trio_2_A_CLK2_N"];
        attribute ecadSignals = ["CSI2_Link_2_Trio_1_A_D0_P", "CSI2_Link_2_Trio_1_B_D0_N", "CSI2_Link_2_Trio_2_B_D1_P", "CSI2_Link_2_Trio_2_C_D1_N", "CSI2_Link_2_Trio_3_A_D2_P", "CSI2_Link_2_Trio_3_B_D2_N", "CSI2_Link_2_Trio_4_B_D3_P", "CSI2_Link_2_Trio_4_C_D3_N", "CSI2_Link_2_Trio_3_C_CLK1_P", "CSI2_Link_2_Trio_4_A_CLK1_N", "CSI2_Link_2_Trio_1_C_CLK2_P", "CSI2_Link_2_Trio_2_A_CLK2_N"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-D0688FFAAF";
        attribute family = "interface";
        attribute template = "CSI2_[Link/Port]";
        attribute instanceIndex = "2";
        attribute bcLine = "CSI2_Link_2 CSI2_Link_2_Trio_1_A_D0_P,CSI2_Link_2_Trio_1_B_D0_N,CSI2_Link_2_Trio_2_B_D1_P,CSI2_Link_2_Trio_2_C_D1_N,CSI2_Link_2_Trio_3_A_D2_P,CSI2_Link_2_Trio_3_B_D2_N,CSI2_Link_2_Trio_4_B_D3_P,CSI2_Link_2_Trio_4_C_D3_N,CSI2_Link_2_Trio_3_C_CLK1_P,CSI2_Link_2_Trio_4_A_CLK1_N,CSI2_Link_2_Trio_1_C_CLK2_P,CSI2_Link_2_Trio_2_A_CLK2_N";
        attribute busContentName = "CSI2_Link_2";
    }
    connection CSI2_Link_3_Reference : ArchitectureConnection {
        attribute connectionId = "REF-53955199F6";
        attribute netId = "NET-1DB177E4F8";
        attribute referenceName = "CSI2_Link_3";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "CSI2_Link_3";
        attribute connectionType = "Bus";
        attribute signals = ["CSI2_Link_3_Trio_1_A_D0_P", "CSI2_Link_3_Trio_1_B_D0_N", "CSI2_Link_3_Trio_2_B_D1_P", "CSI2_Link_3_Trio_2_C_D1_N", "CSI2_Link_3_Trio_3_A_D2_P", "CSI2_Link_3_Trio_3_B_D2_N", "CSI2_Link_3_Trio_4_B_D3_P", "CSI2_Link_3_Trio_4_C_D3_N", "CSI2_Link_3_Trio_3_C_CLK1_P", "CSI2_Link_3_Trio_4_A_CLK1_N", "CSI2_Link_3_Trio_1_C_CLK2_P", "CSI2_Link_3_Trio_2_A_CLK2_N"];
        attribute ecadSignals = ["CSI2_Link_3_Trio_1_A_D0_P", "CSI2_Link_3_Trio_1_B_D0_N", "CSI2_Link_3_Trio_2_B_D1_P", "CSI2_Link_3_Trio_2_C_D1_N", "CSI2_Link_3_Trio_3_A_D2_P", "CSI2_Link_3_Trio_3_B_D2_N", "CSI2_Link_3_Trio_4_B_D3_P", "CSI2_Link_3_Trio_4_C_D3_N", "CSI2_Link_3_Trio_3_C_CLK1_P", "CSI2_Link_3_Trio_4_A_CLK1_N", "CSI2_Link_3_Trio_1_C_CLK2_P", "CSI2_Link_3_Trio_2_A_CLK2_N"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-1DB177E4F8";
        attribute family = "interface";
        attribute template = "CSI2_[Link/Port]";
        attribute instanceIndex = "3";
        attribute bcLine = "CSI2_Link_3 CSI2_Link_3_Trio_1_A_D0_P,CSI2_Link_3_Trio_1_B_D0_N,CSI2_Link_3_Trio_2_B_D1_P,CSI2_Link_3_Trio_2_C_D1_N,CSI2_Link_3_Trio_3_A_D2_P,CSI2_Link_3_Trio_3_B_D2_N,CSI2_Link_3_Trio_4_B_D3_P,CSI2_Link_3_Trio_4_C_D3_N,CSI2_Link_3_Trio_3_C_CLK1_P,CSI2_Link_3_Trio_4_A_CLK1_N,CSI2_Link_3_Trio_1_C_CLK2_P,CSI2_Link_3_Trio_2_A_CLK2_N";
        attribute busContentName = "CSI2_Link_3";
    }
    connection ETH_SGMII_Link_1_Reference : ArchitectureConnection {
        attribute connectionId = "REF-BFBFFCCC52";
        attribute netId = "NET-8EF8E93549";
        attribute referenceName = "ETH_SGMII_Link_1";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "ETH_SGMII_Link_1";
        attribute connectionType = "Bus";
        attribute signals = ["ETH_SGMII_Link_1_TXD_P", "ETH_SGMII_Link_1_TXD_N", "ETH_SGMII_Link_1_RXD_P", "ETH_SGMII_Link_1_RXD_N"];
        attribute ecadSignals = ["ETH_SGMII_Link_1_TXD_P", "ETH_SGMII_Link_1_TXD_N", "ETH_SGMII_Link_1_RXD_P", "ETH_SGMII_Link_1_RXD_N"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-8EF8E93549";
        attribute family = "interface";
        attribute template = "ETH_SGMII_[Link/Port]";
        attribute instanceIndex = "1";
        attribute bcLine = "ETH_SGMII_Link_1 ETH_SGMII_Link_1_TXD_P,ETH_SGMII_Link_1_TXD_N,ETH_SGMII_Link_1_RXD_P,ETH_SGMII_Link_1_RXD_N";
        attribute busContentName = "ETH_SGMII_Link_1";
    }
    connection VBAT_PSU_IN_230V_Reference : ArchitectureConnection {
        attribute connectionId = "REF-ED73744E45";
        attribute netId = "NET-1A704E69DE";
        attribute referenceName = "VBAT_PSU_IN_230V";
        attribute referenceDirection = "In";
        attribute interfaceName = "VBAT_PSU_IN_230V";
        attribute connectionType = "Net";
        attribute signals = ["VBAT_PSU_IN_230V"];
        attribute ecadSignals = ["VBAT_PSU_IN_230V"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-1A704E69DE";
        attribute family = "power";
        attribute template = "VBAT";
        attribute instanceIndex = "0";
        attribute bcLine = "Power_Signals VBAT_PSU_IN_230V";
        attribute busContentName = "Power_Signals";
        attribute powerDirection = "PowerIn";
    }
    connection VBAT_PSU_IN_24V_Reference : ArchitectureConnection {
        attribute connectionId = "REF-33A45D9154";
        attribute netId = "NET-F5F89AE832";
        attribute referenceName = "VBAT_PSU_IN_24V";
        attribute referenceDirection = "In";
        attribute interfaceName = "VBAT_PSU_IN_24V";
        attribute connectionType = "Net";
        attribute signals = ["VBAT_PSU_IN_24V"];
        attribute ecadSignals = ["VBAT_PSU_IN_24V"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-F5F89AE832";
        attribute family = "power";
        attribute template = "VBAT";
        attribute instanceIndex = "0";
        attribute bcLine = "Power_Signals VBAT_PSU_IN_24V";
        attribute busContentName = "Power_Signals";
        attribute powerDirection = "PowerIn";
    }
    connection VBAT_PSU_BOARD_24V_Reference : ArchitectureConnection {
        attribute connectionId = "REF-567047D78F";
        attribute netId = "NET-706E6FBB03";
        attribute referenceName = "VBAT_PSU_BOARD_24V";
        attribute referenceDirection = "Out";
        attribute interfaceName = "VBAT_PSU_BOARD_24V";
        attribute connectionType = "Net";
        attribute signals = ["VBAT_PSU_BOARD_24V"];
        attribute ecadSignals = ["VBAT_PSU_BOARD_24V"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-706E6FBB03";
        attribute family = "power";
        attribute template = "VBAT";
        attribute instanceIndex = "0";
        attribute bcLine = "Power_Signals VBAT_PSU_BOARD_24V";
        attribute busContentName = "Power_Signals";
        attribute powerDirection = "PowerOut";
    }
    connection ETH_10G_MII_Link_1_Reference : ArchitectureConnection {
        attribute connectionId = "REF-176A2911E6";
        attribute netId = "NET-2C590E7B87";
        attribute referenceName = "ETH_10G_MII_Link_1";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "ETH_10G_MII_Link_1";
        attribute connectionType = "Bus";
        attribute signals = ["ETH_10G_MII_Link_1_TX_P", "ETH_10G_MII_Link_1_TX_N", "ETH_10G_MII_Link_1_RX_P", "ETH_10G_MII_Link_1_RX_N"];
        attribute ecadSignals = ["ETH_10G_MII_Link_1_TX_P", "ETH_10G_MII_Link_1_TX_N", "ETH_10G_MII_Link_1_RX_P", "ETH_10G_MII_Link_1_RX_N"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-2C590E7B87";
        attribute family = "interface";
        attribute template = "ETH_10G_MII_[Link/Port]";
        attribute instanceIndex = "1";
        attribute bcLine = "ETH_10G_MII_Link_1 ETH_10G_MII_Link_1_TX_P,ETH_10G_MII_Link_1_TX_N,ETH_10G_MII_Link_1_RX_P,ETH_10G_MII_Link_1_RX_N";
        attribute busContentName = "ETH_10G_MII_Link_1";
    }
    connection ETH_10G_MII_Link_2_Reference : ArchitectureConnection {
        attribute connectionId = "REF-F15DEEB97C";
        attribute netId = "NET-A3170EDE26";
        attribute referenceName = "ETH_10G_MII_Link_2";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "ETH_10G_MII_Link_2";
        attribute connectionType = "Bus";
        attribute signals = ["ETH_10G_MII_Link_2_TX_P", "ETH_10G_MII_Link_2_TX_N", "ETH_10G_MII_Link_2_RX_P", "ETH_10G_MII_Link_2_RX_N"];
        attribute ecadSignals = ["ETH_10G_MII_Link_2_TX_P", "ETH_10G_MII_Link_2_TX_N", "ETH_10G_MII_Link_2_RX_P", "ETH_10G_MII_Link_2_RX_N"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-A3170EDE26";
        attribute family = "interface";
        attribute template = "ETH_10G_MII_[Link/Port]";
        attribute instanceIndex = "2";
        attribute bcLine = "ETH_10G_MII_Link_2 ETH_10G_MII_Link_2_TX_P,ETH_10G_MII_Link_2_TX_N,ETH_10G_MII_Link_2_RX_P,ETH_10G_MII_Link_2_RX_N";
        attribute busContentName = "ETH_10G_MII_Link_2";
    }
    connection ETH_10G_MII_Link_3_Reference : ArchitectureConnection {
        attribute connectionId = "REF-3DC6406796";
        attribute netId = "NET-ED2317EE8E";
        attribute referenceName = "ETH_10G_MII_Link_3";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "ETH_10G_MII_Link_3";
        attribute connectionType = "Bus";
        attribute signals = ["ETH_10G_MII_Link_3_TX_P", "ETH_10G_MII_Link_3_TX_N", "ETH_10G_MII_Link_3_RX_P", "ETH_10G_MII_Link_3_RX_N"];
        attribute ecadSignals = ["ETH_10G_MII_Link_3_TX_P", "ETH_10G_MII_Link_3_TX_N", "ETH_10G_MII_Link_3_RX_P", "ETH_10G_MII_Link_3_RX_N"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-ED2317EE8E";
        attribute family = "interface";
        attribute template = "ETH_10G_MII_[Link/Port]";
        attribute instanceIndex = "3";
        attribute bcLine = "ETH_10G_MII_Link_3 ETH_10G_MII_Link_3_TX_P,ETH_10G_MII_Link_3_TX_N,ETH_10G_MII_Link_3_RX_P,ETH_10G_MII_Link_3_RX_N";
        attribute busContentName = "ETH_10G_MII_Link_3";
    }
    connection ETH_10G_MII_Link_4_Reference : ArchitectureConnection {
        attribute connectionId = "REF-478FE417D5";
        attribute netId = "NET-C5406E7CB0";
        attribute referenceName = "ETH_10G_MII_Link_4";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "ETH_10G_MII_Link_4";
        attribute connectionType = "Bus";
        attribute signals = ["ETH_10G_MII_Link_4_TX_P", "ETH_10G_MII_Link_4_TX_N", "ETH_10G_MII_Link_4_RX_P", "ETH_10G_MII_Link_4_RX_N"];
        attribute ecadSignals = ["ETH_10G_MII_Link_4_TX_P", "ETH_10G_MII_Link_4_TX_N", "ETH_10G_MII_Link_4_RX_P", "ETH_10G_MII_Link_4_RX_N"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-C5406E7CB0";
        attribute family = "interface";
        attribute template = "ETH_10G_MII_[Link/Port]";
        attribute instanceIndex = "4";
        attribute bcLine = "ETH_10G_MII_Link_4 ETH_10G_MII_Link_4_TX_P,ETH_10G_MII_Link_4_TX_N,ETH_10G_MII_Link_4_RX_P,ETH_10G_MII_Link_4_RX_N";
        attribute busContentName = "ETH_10G_MII_Link_4";
    }
    connection ETH_10G_MII_Link_5_Reference : ArchitectureConnection {
        attribute connectionId = "REF-8BD85E7CFB";
        attribute netId = "NET-E6F4417864";
        attribute referenceName = "ETH_10G_MII_Link_5";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "ETH_10G_MII_Link_5";
        attribute connectionType = "Bus";
        attribute signals = ["ETH_10G_MII_Link_5_TX_P", "ETH_10G_MII_Link_5_TX_N", "ETH_10G_MII_Link_5_RX_P", "ETH_10G_MII_Link_5_RX_N"];
        attribute ecadSignals = ["ETH_10G_MII_Link_5_TX_P", "ETH_10G_MII_Link_5_TX_N", "ETH_10G_MII_Link_5_RX_P", "ETH_10G_MII_Link_5_RX_N"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-E6F4417864";
        attribute family = "interface";
        attribute template = "ETH_10G_MII_[Link/Port]";
        attribute instanceIndex = "5";
        attribute bcLine = "ETH_10G_MII_Link_5 ETH_10G_MII_Link_5_TX_P,ETH_10G_MII_Link_5_TX_N,ETH_10G_MII_Link_5_RX_P,ETH_10G_MII_Link_5_RX_N";
        attribute busContentName = "ETH_10G_MII_Link_5";
    }
    connection UART_Link_1_Reference : ArchitectureConnection {
        attribute connectionId = "REF-13BA3059B6";
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
        attribute propagateToParent = true;
    }
    connection UART_Link_2_Reference : ArchitectureConnection {
        attribute connectionId = "REF-239DA0DC25";
        attribute netId = "NET-5696D142A4";
        attribute referenceName = "UART_Link_2";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "UART_Link_2";
        attribute connectionType = "Bus";
        attribute signals = ["UART_Link_2_RX", "UART_Link_2_TX", "UART_Link_2_CTS", "UART_Link_2_RTS"];
        attribute ecadSignals = ["UART_Link_2_RX", "UART_Link_2_TX", "UART_Link_2_CTS", "UART_Link_2_RTS"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-5696D142A4";
        attribute family = "interface";
        attribute template = "UART_[Link/Port]";
        attribute instanceIndex = "2";
        attribute bcLine = "UART_Link_2 UART_Link_2_RX,UART_Link_2_TX,UART_Link_2_CTS,UART_Link_2_RTS";
        attribute busContentName = "UART_Link_2";
        attribute propagateToParent = true;
    }
    connection CSI2_Link_1_Reference : ArchitectureConnection {
        attribute connectionId = "REF-D8CCB224C8";
        attribute netId = "NET-187341D3D0";
        attribute referenceName = "CSI2_Link_1";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "CSI2_Link_1";
        attribute connectionType = "Bus";
        attribute signals = ["CSI2_Link_1_Trio_1_A_D0_P", "CSI2_Link_1_Trio_1_B_D0_N", "CSI2_Link_1_Trio_2_B_D1_P", "CSI2_Link_1_Trio_2_C_D1_N", "CSI2_Link_1_Trio_3_A_D2_P", "CSI2_Link_1_Trio_3_B_D2_N", "CSI2_Link_1_Trio_4_B_D3_P", "CSI2_Link_1_Trio_4_C_D3_N", "CSI2_Link_1_Trio_3_C_CLK1_P", "CSI2_Link_1_Trio_4_A_CLK1_N", "CSI2_Link_1_Trio_1_C_CLK2_P", "CSI2_Link_1_Trio_2_A_CLK2_N"];
        attribute ecadSignals = ["CSI2_Link_1_Trio_1_A_D0_P", "CSI2_Link_1_Trio_1_B_D0_N", "CSI2_Link_1_Trio_2_B_D1_P", "CSI2_Link_1_Trio_2_C_D1_N", "CSI2_Link_1_Trio_3_A_D2_P", "CSI2_Link_1_Trio_3_B_D2_N", "CSI2_Link_1_Trio_4_B_D3_P", "CSI2_Link_1_Trio_4_C_D3_N", "CSI2_Link_1_Trio_3_C_CLK1_P", "CSI2_Link_1_Trio_4_A_CLK1_N", "CSI2_Link_1_Trio_1_C_CLK2_P", "CSI2_Link_1_Trio_2_A_CLK2_N"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-187341D3D0";
        attribute family = "interface";
        attribute template = "CSI2_[Link/Port]";
        attribute instanceIndex = "1";
        attribute bcLine = "CSI2_Link_1 CSI2_Link_1_Trio_1_A_D0_P,CSI2_Link_1_Trio_1_B_D0_N,CSI2_Link_1_Trio_2_B_D1_P,CSI2_Link_1_Trio_2_C_D1_N,CSI2_Link_1_Trio_3_A_D2_P,CSI2_Link_1_Trio_3_B_D2_N,CSI2_Link_1_Trio_4_B_D3_P,CSI2_Link_1_Trio_4_C_D3_N,CSI2_Link_1_Trio_3_C_CLK1_P,CSI2_Link_1_Trio_4_A_CLK1_N,CSI2_Link_1_Trio_1_C_CLK2_P,CSI2_Link_1_Trio_2_A_CLK2_N";
        attribute busContentName = "CSI2_Link_1";
        attribute copiedFrom = "CSI2_Link_1";
    }
    connection CSI2_Link_2_Reference : ArchitectureConnection {
        attribute connectionId = "REF-4F219560A7";
        attribute netId = "NET-D0688FFAAF";
        attribute referenceName = "CSI2_Link_2";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "CSI2_Link_2";
        attribute connectionType = "Bus";
        attribute signals = ["CSI2_Link_2_Trio_1_A_D0_P", "CSI2_Link_2_Trio_1_B_D0_N", "CSI2_Link_2_Trio_2_B_D1_P", "CSI2_Link_2_Trio_2_C_D1_N", "CSI2_Link_2_Trio_3_A_D2_P", "CSI2_Link_2_Trio_3_B_D2_N", "CSI2_Link_2_Trio_4_B_D3_P", "CSI2_Link_2_Trio_4_C_D3_N", "CSI2_Link_2_Trio_3_C_CLK1_P", "CSI2_Link_2_Trio_4_A_CLK1_N", "CSI2_Link_2_Trio_1_C_CLK2_P", "CSI2_Link_2_Trio_2_A_CLK2_N"];
        attribute ecadSignals = ["CSI2_Link_2_Trio_1_A_D0_P", "CSI2_Link_2_Trio_1_B_D0_N", "CSI2_Link_2_Trio_2_B_D1_P", "CSI2_Link_2_Trio_2_C_D1_N", "CSI2_Link_2_Trio_3_A_D2_P", "CSI2_Link_2_Trio_3_B_D2_N", "CSI2_Link_2_Trio_4_B_D3_P", "CSI2_Link_2_Trio_4_C_D3_N", "CSI2_Link_2_Trio_3_C_CLK1_P", "CSI2_Link_2_Trio_4_A_CLK1_N", "CSI2_Link_2_Trio_1_C_CLK2_P", "CSI2_Link_2_Trio_2_A_CLK2_N"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-D0688FFAAF";
        attribute family = "interface";
        attribute template = "CSI2_[Link/Port]";
        attribute instanceIndex = "2";
        attribute bcLine = "CSI2_Link_2 CSI2_Link_2_Trio_1_A_D0_P,CSI2_Link_2_Trio_1_B_D0_N,CSI2_Link_2_Trio_2_B_D1_P,CSI2_Link_2_Trio_2_C_D1_N,CSI2_Link_2_Trio_3_A_D2_P,CSI2_Link_2_Trio_3_B_D2_N,CSI2_Link_2_Trio_4_B_D3_P,CSI2_Link_2_Trio_4_C_D3_N,CSI2_Link_2_Trio_3_C_CLK1_P,CSI2_Link_2_Trio_4_A_CLK1_N,CSI2_Link_2_Trio_1_C_CLK2_P,CSI2_Link_2_Trio_2_A_CLK2_N";
        attribute busContentName = "CSI2_Link_2";
        attribute copiedFrom = "CSI2_Link_2";
    }
    connection CSI2_Link_3_Reference : ArchitectureConnection {
        attribute connectionId = "REF-8474A36C98";
        attribute netId = "NET-1DB177E4F8";
        attribute referenceName = "CSI2_Link_3";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "CSI2_Link_3";
        attribute connectionType = "Bus";
        attribute signals = ["CSI2_Link_3_Trio_1_A_D0_P", "CSI2_Link_3_Trio_1_B_D0_N", "CSI2_Link_3_Trio_2_B_D1_P", "CSI2_Link_3_Trio_2_C_D1_N", "CSI2_Link_3_Trio_3_A_D2_P", "CSI2_Link_3_Trio_3_B_D2_N", "CSI2_Link_3_Trio_4_B_D3_P", "CSI2_Link_3_Trio_4_C_D3_N", "CSI2_Link_3_Trio_3_C_CLK1_P", "CSI2_Link_3_Trio_4_A_CLK1_N", "CSI2_Link_3_Trio_1_C_CLK2_P", "CSI2_Link_3_Trio_2_A_CLK2_N"];
        attribute ecadSignals = ["CSI2_Link_3_Trio_1_A_D0_P", "CSI2_Link_3_Trio_1_B_D0_N", "CSI2_Link_3_Trio_2_B_D1_P", "CSI2_Link_3_Trio_2_C_D1_N", "CSI2_Link_3_Trio_3_A_D2_P", "CSI2_Link_3_Trio_3_B_D2_N", "CSI2_Link_3_Trio_4_B_D3_P", "CSI2_Link_3_Trio_4_C_D3_N", "CSI2_Link_3_Trio_3_C_CLK1_P", "CSI2_Link_3_Trio_4_A_CLK1_N", "CSI2_Link_3_Trio_1_C_CLK2_P", "CSI2_Link_3_Trio_2_A_CLK2_N"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-1DB177E4F8";
        attribute family = "interface";
        attribute template = "CSI2_[Link/Port]";
        attribute instanceIndex = "3";
        attribute bcLine = "CSI2_Link_3 CSI2_Link_3_Trio_1_A_D0_P,CSI2_Link_3_Trio_1_B_D0_N,CSI2_Link_3_Trio_2_B_D1_P,CSI2_Link_3_Trio_2_C_D1_N,CSI2_Link_3_Trio_3_A_D2_P,CSI2_Link_3_Trio_3_B_D2_N,CSI2_Link_3_Trio_4_B_D3_P,CSI2_Link_3_Trio_4_C_D3_N,CSI2_Link_3_Trio_3_C_CLK1_P,CSI2_Link_3_Trio_4_A_CLK1_N,CSI2_Link_3_Trio_1_C_CLK2_P,CSI2_Link_3_Trio_2_A_CLK2_N";
        attribute busContentName = "CSI2_Link_3";
        attribute copiedFrom = "CSI2_Link_3";
    }
    connection ETH_SGMII_Link_1_Reference : ArchitectureConnection {
        attribute connectionId = "REF-2F988ABBF7";
        attribute netId = "NET-8EF8E93549";
        attribute referenceName = "ETH_SGMII_Link_1";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "ETH_SGMII_Link_1";
        attribute connectionType = "Bus";
        attribute signals = ["ETH_SGMII_Link_1_TXD_P", "ETH_SGMII_Link_1_TXD_N", "ETH_SGMII_Link_1_RXD_P", "ETH_SGMII_Link_1_RXD_N"];
        attribute ecadSignals = ["ETH_SGMII_Link_1_TXD_P", "ETH_SGMII_Link_1_TXD_N", "ETH_SGMII_Link_1_RXD_P", "ETH_SGMII_Link_1_RXD_N"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-8EF8E93549";
        attribute family = "interface";
        attribute template = "ETH_SGMII_[Link/Port]";
        attribute instanceIndex = "1";
        attribute bcLine = "ETH_SGMII_Link_1 ETH_SGMII_Link_1_TXD_P,ETH_SGMII_Link_1_TXD_N,ETH_SGMII_Link_1_RXD_P,ETH_SGMII_Link_1_RXD_N";
        attribute busContentName = "ETH_SGMII_Link_1";
        attribute copiedFrom = "ETH_SGMII_Link_1";
    }
}
}
