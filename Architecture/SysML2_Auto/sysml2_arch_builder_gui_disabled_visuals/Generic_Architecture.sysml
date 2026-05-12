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
        attribute blockId = "BLK-EC175E18CE";
        attribute architectureLevel = "Level1_Domain";
        attribute isHost = false;
        attribute color = "#f8cecc";
        attribute domainColor = "#f8cecc";
        part PSU_1 : ArchitectureBlock {
            attribute blockId = "BLK-2C9CF8DE48";
            attribute architectureLevel = "Level2_ArchitectureElement";
            attribute isHost = false;
            attribute color = "#f8cecc";
            attribute domainColor = "#f8cecc";
            port SPI_Link_1 : ArchitecturePort {
                attribute portId = "PRT-F272E72EB3";
                attribute portType = "Bidi";
                attribute interfaceName = "SPI_Link_1";
                attribute connectionType = "Bus";
                attribute signals = ["SPI_Link_1_SCLK", "SPI_Link_1_CS0#", "SPI_Link_1_CS1#", "SPI_Link_1_CS2#", "SPI_Link_1_CS3#", "SPI_Link_1_MOSI", "SPI_Link_1_MISO"];
                attribute ecadSignals = ["SPI_Link_1_SCLK", "SPI_Link_1_CS0#", "SPI_Link_1_CS1#", "SPI_Link_1_CS2#", "SPI_Link_1_CS3#", "SPI_Link_1_MOSI", "SPI_Link_1_MISO"];
                attribute generatedBy = "BusContentWizard";
                attribute netId = "NET-A135C368A8";
                attribute family = "interface";
                attribute template = "SPI_[Link/Port]";
                attribute instanceIndex = "1";
                attribute bcLine = "SPI_Link_1 SPI_Link_1_SCLK,SPI_Link_1_CS0#,SPI_Link_1_CS1#,SPI_Link_1_CS2#,SPI_Link_1_CS3#,SPI_Link_1_MOSI,SPI_Link_1_MISO";
                attribute busContentName = "SPI_Link_1";
                attribute propagateToParent = false;
            }
            port SPI_Link_2 : ArchitecturePort {
                attribute portId = "PRT-8F8CF863D0";
                attribute portType = "Bidi";
                attribute interfaceName = "SPI_Link_2";
                attribute connectionType = "Bus";
                attribute signals = ["SPI_Link_2_SCLK", "SPI_Link_2_CS0#", "SPI_Link_2_CS1#", "SPI_Link_2_CS2#", "SPI_Link_2_CS3#", "SPI_Link_2_MOSI", "SPI_Link_2_MISO"];
                attribute ecadSignals = ["SPI_Link_2_SCLK", "SPI_Link_2_CS0#", "SPI_Link_2_CS1#", "SPI_Link_2_CS2#", "SPI_Link_2_CS3#", "SPI_Link_2_MOSI", "SPI_Link_2_MISO"];
                attribute generatedBy = "BusContentWizard";
                attribute netId = "NET-EABE268B1E";
                attribute family = "interface";
                attribute template = "SPI_[Link/Port]";
                attribute instanceIndex = "2";
                attribute bcLine = "SPI_Link_2 SPI_Link_2_SCLK,SPI_Link_2_CS0#,SPI_Link_2_CS1#,SPI_Link_2_CS2#,SPI_Link_2_CS3#,SPI_Link_2_MOSI,SPI_Link_2_MISO";
                attribute busContentName = "SPI_Link_2";
                attribute propagateToParent = false;
            }
        }
    }

    connection SPI_Link_1_Reference : ArchitectureConnection {
        attribute connectionId = "REF-9E144FF7D4";
        attribute netId = "NET-A135C368A8";
        attribute referenceName = "SPI_Link_1";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "SPI_Link_1";
        attribute connectionType = "Bus";
        attribute signals = ["SPI_Link_1_SCLK", "SPI_Link_1_CS0#", "SPI_Link_1_CS1#", "SPI_Link_1_CS2#", "SPI_Link_1_CS3#", "SPI_Link_1_MOSI", "SPI_Link_1_MISO"];
        attribute ecadSignals = ["SPI_Link_1_SCLK", "SPI_Link_1_CS0#", "SPI_Link_1_CS1#", "SPI_Link_1_CS2#", "SPI_Link_1_CS3#", "SPI_Link_1_MOSI", "SPI_Link_1_MISO"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-A135C368A8";
        attribute family = "interface";
        attribute template = "SPI_[Link/Port]";
        attribute instanceIndex = "1";
        attribute bcLine = "SPI_Link_1 SPI_Link_1_SCLK,SPI_Link_1_CS0#,SPI_Link_1_CS1#,SPI_Link_1_CS2#,SPI_Link_1_CS3#,SPI_Link_1_MOSI,SPI_Link_1_MISO";
        attribute busContentName = "SPI_Link_1";
        attribute propagateToParent = false;
    }
    connection SPI_Link_2_Reference : ArchitectureConnection {
        attribute connectionId = "REF-52818B3B55";
        attribute netId = "NET-EABE268B1E";
        attribute referenceName = "SPI_Link_2";
        attribute referenceDirection = "Bidi";
        attribute interfaceName = "SPI_Link_2";
        attribute connectionType = "Bus";
        attribute signals = ["SPI_Link_2_SCLK", "SPI_Link_2_CS0#", "SPI_Link_2_CS1#", "SPI_Link_2_CS2#", "SPI_Link_2_CS3#", "SPI_Link_2_MOSI", "SPI_Link_2_MISO"];
        attribute ecadSignals = ["SPI_Link_2_SCLK", "SPI_Link_2_CS0#", "SPI_Link_2_CS1#", "SPI_Link_2_CS2#", "SPI_Link_2_CS3#", "SPI_Link_2_MOSI", "SPI_Link_2_MISO"];
        attribute generatedBy = "BusContentWizard";
        attribute netId = "NET-EABE268B1E";
        attribute family = "interface";
        attribute template = "SPI_[Link/Port]";
        attribute instanceIndex = "2";
        attribute bcLine = "SPI_Link_2 SPI_Link_2_SCLK,SPI_Link_2_CS0#,SPI_Link_2_CS1#,SPI_Link_2_CS2#,SPI_Link_2_CS3#,SPI_Link_2_MOSI,SPI_Link_2_MISO";
        attribute busContentName = "SPI_Link_2";
        attribute propagateToParent = false;
    }
}
}
