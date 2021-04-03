# programs for output files
find_program(OBJCOPY ${ARM_GCC_PATH}/bin/arm-none-eabi-objcopy)
find_program(OBJDUMP ${ARM_GCC_PATH}/bin/arm-none-eabi-objdump)
find_program(SIZE ${ARM_GCC_PATH}/bin/arm-none-eabi-size)
find_program(NM ${ARM_GCC_PATH}/bin/arm-none-eabi-nm)
find_program(HEXDUMP hexdump)

# set build path relative to each project
set(CMAKE_BUILD_DIRECTORY ${CMAKE_BINARY_DIR})
set(LIBRARY_OUTPUT_PATH ${CMAKE_BINARY_DIR}/lib)
set(EXECUTABLE_OUTPUT_PATH ${CMAKE_BINARY_DIR}/bin)
set(RESOURCES_OUTPUT_PATH ${CMAKE_BINARY_DIR}/resources)

# helper functions to build

#print the size information
macro(GEN_ELF_SIZE target)
	add_custom_command(
	    TARGET ${target}.elf POST_BUILD
	    COMMAND ${SIZE} --format=sysv -d ${EXECUTABLE_OUTPUT_PATH}/${target}.elf
	)

endmacro(GEN_ELF_SIZE)

# command to create a bin from elf
macro(GEN_OBJCOPY_BIN target)
	add_custom_command(
	    OUTPUT ${EXECUTABLE_OUTPUT_PATH}/${target}.bin 
	    COMMAND ${OBJCOPY} -O binary ${EXECUTABLE_OUTPUT_PATH}/${target}.elf ${EXECUTABLE_OUTPUT_PATH}/${target}.bin
	    DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${target}.elf
#	    COMMENT "Create ${EXECUTABLE_OUTPUT_PATH}/${target}.bin file"
	)
	
	add_custom_target(${target}.bin ALL DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${target}.bin)
	
endmacro(GEN_OBJCOPY_BIN)

# command to create a ihx from elf
macro(GEN_OBJCOPY_IHX target)
	add_custom_command(
	    OUTPUT ${EXECUTABLE_OUTPUT_PATH}/${target}.ihx 
	    COMMAND ${OBJCOPY} -O ihex ${EXECUTABLE_OUTPUT_PATH}/${target}.elf ${EXECUTABLE_OUTPUT_PATH}/${target}.ihx
	    DEPENDS  ${EXECUTABLE_OUTPUT_PATH}/${target}.elf
	)
	add_custom_target(${target}.ihx ALL DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${target}.ihx)
endmacro(GEN_OBJCOPY_IHX)

# command to create a dump from elf
macro(GEN_OBJDUMP_DUMP target)
	add_custom_command(
	    OUTPUT ${EXECUTABLE_OUTPUT_PATH}/${target}.dump 
	    COMMAND ${OBJDUMP} -DSC ${EXECUTABLE_OUTPUT_PATH}/${target}.elf > ${EXECUTABLE_OUTPUT_PATH}/${target}.dump
	    DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${target}.elf
	)
	add_custom_target(${target}.dump ALL DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${target}.dump)
endmacro(GEN_OBJDUMP_DUMP)

# command to create a rom from bin
macro(GEN_OBJDUMP_MAP target)
	add_custom_command(
	    OUTPUT ${EXECUTABLE_OUTPUT_PATH}/${target}.map 
	    COMMAND ${OBJDUMP} -t ${EXECUTABLE_OUTPUT_PATH}/${target}.elf > ${EXECUTABLE_OUTPUT_PATH}/${target}.map
	    DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${target}.elf
	)
	add_custom_target(${target}.map ALL DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${target}.map)
endmacro(GEN_OBJDUMP_MAP)

# command to create a rom from bin
macro(GEN_HEXDUMP_ROM target)
	add_custom_command(
	    OUTPUT ${EXECUTABLE_OUTPUT_PATH}/${target}.rom 
	    COMMAND ${HEXDUMP} -v -e'1/1 \"%.2X\\n\"' ${EXECUTABLE_OUTPUT_PATH}/${target}.bin > ${EXECUTABLE_OUTPUT_PATH}/${target}.rom
	    DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${target}.bin
	)
	add_custom_target(${target}.rom ALL DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${target}.rom)
endmacro(GEN_HEXDUMP_ROM)

# command to create a rom from bin
macro(GEN_OBJCOPY_HEX target)
        add_custom_command(
            OUTPUT ${EXECUTABLE_OUTPUT_PATH}/${target}.hex
            COMMAND ${OBJCOPY} -O ihex ${EXECUTABLE_OUTPUT_PATH}/${target}.elf ${EXECUTABLE_OUTPUT_PATH}/${target}.hex
            DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${target}.elf
        )
        add_custom_target(${target}.hex ALL DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${target}.hex)
endmacro(GEN_OBJCOPY_HEX)

# command to extract symbols list from elf file
macro(GEN_ELF_NM target)
        add_custom_command(
            OUTPUT ${EXECUTABLE_OUTPUT_PATH}/${target}.nm
            COMMAND ${NM} -l -a -C --print-size --size-sort --radix=d ${EXECUTABLE_OUTPUT_PATH}/${target}.elf > ${EXECUTABLE_OUTPUT_PATH}/${target}.nm
            DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${target}.elf
        )
        add_custom_target(${target}.nm ALL DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${target}.nm)
endmacro(GEN_ELF_NM)
