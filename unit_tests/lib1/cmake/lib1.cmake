message("l8x library path ${LIBRARY_PATH}")

list(APPEND sources
	${LIBRARY_PATH}/src/l8x.cpp
)

include_directories(
	${LIBRARY_PATH}/src
)
