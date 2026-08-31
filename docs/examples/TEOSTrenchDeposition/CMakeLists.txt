project(TEOSTrenchDeposition LANGUAGES CXX)

add_executable(singleTEOS "singleTEOS.cpp")
target_link_libraries(singleTEOS PRIVATE ViennaPS)


add_dependencies(ViennaPS_Examples singleTEOS)
viennacore_setup_bat(singleTEOS ${VIENNAPS_ARTIFACTS_DIRECTORY})

add_executable(multiTEOS "multiTEOS.cpp")
target_link_libraries(multiTEOS PRIVATE ViennaPS)


add_dependencies(ViennaPS_Examples multiTEOS)
viennacore_setup_bat(multiTEOS ${VIENNAPS_ARTIFACTS_DIRECTORY})
