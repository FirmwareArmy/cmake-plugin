project(firmware NONE)

include_directories(
	.
)

# source and header files
list(APPEND sources
    main.cpp
)

message("Sources: ${sources}")
add_executable(${PROJECT_NAME}.elf ${sources})
target_link_libraries(${PROJECT_NAME}.elf
	
	${LINKER_FLAGS}
)

# generate binary
GEN_OBJCOPY_BIN(${PROJECT_NAME})

# # generate dump
# GEN_OBJDUMP_DUMP(${PROJECT_NAME})

# generate map
GEN_OBJDUMP_MAP(${PROJECT_NAME})

# generate hex
GEN_OBJCOPY_HEX(${PROJECT_NAME})

# list symbols
GEN_ELF_NM(${PROJECT_NAME})

# output informations
GEN_ELF_SIZE(${PROJECT_NAME})
