# Define a function to create Cython modules.
#
# For more information on the Cython project, see http://cython.org/.
# "Cython is a language that makes writing C extensions for the Python language
# as easy as Python itself."
#
# This file defines a CMake function to build a Cython Python module.
# To use it, first include this file.
#
#   include( UseCython )
#
# Then call cython_add_module to create a module.
#
#   cython_add_module( <target_name> <pyx_target_name> <src1> <src2> ... <srcN> )
#
# Where <module_name> is the import path for the resulting Python module
# (e.g. mymodule.submodule.other_submodule.this_extension),
# <pyx_target_name> is the desired name of the target that runs the Cython compiler
# to generate the needed C or C++ files, and <src1> <src2> ... are additional source files
# to be compiled with the C or C++ file created by Cython.
# The Cython file to be built is found using the <module_name>.
# <module_name> is also used as the name of the target for the desired Python module.
# A list of output files is provided as the <generated_files> attribute
# of the target corresponding to the Cython compilation call.
#
# Cache variables that effect the behavior include:
#
#  CYTHON_ANNOTATE
#  CYTHON_NO_DOCSTRINGS
#  CYTHON_FLAGS
#
# Source file properties that effect the build process are
#
#  CYTHON_IS_CXX
#  CYTHON_IS_PUBLIC
#  CYTHON_IS_API
#
# For a given Cython file, if CYTHON_IS_CXX is set (using set_source_files_properties)
# Cython will output a C++ file. The CYTHON_IS_PUBLIC and CYTHON_IS_API variables
# are used to provide the list of output files given in the <generated_files>
# property of the target corresponding to the Cython call to build the needed
# C/C++ source files.
#
# The Python modules created are written into the CMAKE_CURRENT_BINARY_DIR
# with the same folder structure they have in your project. For example,
# the module name mymodule.submodule.other_submodule.this_extension would
# cause the target mymodule.submodule.other_submodule.this_extension to be created,
# the file ${CMAKE_CURRENT_SOURCE_DIR}/mymodule/submodule/other_submodule/this_extension.pyx
# would be used to build the desired module, and the Python module resulting from
# the compilation would be written to
# ${CMAKE_CURRENT_BINARY_DIR}/mymodule/submodule/other_submodule/this_extension.${ext}
# where ${ext} is the file extension for Python extensions for the target platform
# and Python version.
#
# See also FindCython.cmake

#=============================================================================
# Copyright 2011 Kitware, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#=============================================================================

# Configuration options.
set( CYTHON_ANNOTATE OFF
  CACHE BOOL "Create an annotated .html file when compiling *.pyx." )
set( CYTHON_NO_DOCSTRINGS OFF
  CACHE BOOL "Strip docstrings from the compiled module." )
set( CYTHON_FLAGS "" CACHE STRING
  "Extra flags to the cython compiler." )
mark_as_advanced( CYTHON_ANNOTATE CYTHON_NO_DOCSTRINGS CYTHON_FLAGS )

find_package(Cython REQUIRED)
find_package(Python REQUIRED Development)

set( CYTHON_CXX_EXTENSION "cxx" )
set( CYTHON_C_EXTENSION "c" )

# Create a *.c or *.cxx file from a *.pyx file.
function( compile_pyx _name _pyx_target_name _module_name _directories _pyx_file)
  # Default to assuming all files are C.
  set( _cxx_arg "" )
  set( _extension ${CYTHON_C_EXTENSION} )

  # Make sure the output directory is created.
  file(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/${_directories})

  # Determine if it is a C or C++ file.
  get_source_file_property( _is_cxx ${_pyx_file} CYTHON_IS_CXX )
  if( ${_is_cxx} )
    set( _cxx_arg "--cplus" )
    set( _extension ${CYTHON_CXX_EXTENSION} )
  endif()

  get_source_file_property( _pyx_location ${_pyx_file} LOCATION )

  # Set additional flags.
  if( CYTHON_ANNOTATE )
    set( _annotate_arg "--annotate" )
  endif()

  if( CYTHON_NO_DOCSTRINGS )
    set( _no_docstrings_arg "--no-docstrings" )
  endif()

  if(NOT WIN32)
      if( "${CMAKE_BUILD_TYPE}" STREQUAL "Debug" OR
            "${CMAKE_BUILD_TYPE}" STREQUAL "RelWithDebInfo" )
          set( _cython_debug_arg "--gdb" )
      endif()
  endif()

  # Determining generated file names.
  get_source_file_property( _is_public ${_pyx_file} CYTHON_PUBLIC )
  get_source_file_property( _is_api ${_pyx_file} CYTHON_API )
  if( "${_is_api}" AND "${is_public}" )
      set( _generated_files
          ${CMAKE_CURRENT_BINARY_DIR}/${_directories}/${_module_name}.${_extension}
          ${CMAKE_CURRENT_BINARY_DIR}/${_directories}/${_module_name}.h
          ${CMAKE_CURRENT_BINARY_DIR}/${_directories}/${_module_name}_api.h)
  elseif( "${_is_public}" )
      set( _generated_files
          ${CMAKE_CURRENT_BINARY_DIR}/${_directories}/${_module_name}.${_extension}
          ${CMAKE_CURRENT_BINARY_DIR}/${_directories}/${_module_name}.h)
  elseif( "${_is_api}" )
      set( _generated_files
          ${CMAKE_CURRENT_BINARY_DIR}/${_directories}/${_module_name}.${_extension}
          ${CMAKE_CURRENT_BINARY_DIR}/${_directories}/${_module_name}_api.h)
  else()
      set( _generated_files
          ${CMAKE_CURRENT_BINARY_DIR}/${_directories}/${_module_name}.${_extension})
  endif()
  set_source_files_properties( ${_generated_files} PROPERTIES GENERATED TRUE )

  set(_cython_command ${CYTHON_EXECUTABLE} ${_cxx_arg}
  ${_annotate_arg} ${_no_docstrings_arg} ${_cython_debug_arg} ${CYTHON_FLAGS} --timestamps
  --output-file "${CMAKE_CURRENT_BINARY_DIR}/${_directories}/${_module_name}.${_extension}" ${_pyx_location})
  string(REPLACE ";" " " _cython_comment "${_cython_command}")

  # Add the command to run the compiler.
  add_custom_target(${_pyx_target_name}
    COMMAND ${_cython_command}
    DEPENDS ${_pyx_location}
    # do not specify byproducts for now since they don't work with the older
    # version of cmake available in the apt repositories.
    #BYPRODUCTS ${_generated_files}
    COMMENT "${_cython_comment}"
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/${_directories}
    VERBATIM
    )

  set_target_properties(${_pyx_target_name}
  PROPERTIES generated_files "${_generated_files}")

  # Remove internal variables' visibility to the user.
  foreach(_v _cxx_arg _extension _is_cxx _pyx_location _annotate_arg _no_docstrings_arg _cython_debug_arg _is_public _is_api _generated_files _cython_command _cython_comment)
    set( ${_v} "" CACHE INTERNAL "" )
  endforeach(_v)

endfunction()

# cython_add_module( <name> src1 src2 ... srcN )
# Build the Cython Python module.
function( cython_add_module _name _pyx_target_name _is_cxx)

  string(REPLACE "." "/" _module_source ${_name})
  set(_module_source ${_module_source}.pyx)
  get_filename_component( _directories "${_module_source}" PATH )
  get_filename_component( _module_name "${_module_source}" NAME_WE)

  if(${_is_cxx})
    set_source_files_properties(${_module_source} PROPERTIES CYTHON_IS_CXX 1)
  endif()

  compile_pyx( ${_name} ${_pyx_target_name} ${_module_name} "${_directories}" ${_module_source} )
  include_directories( ${PYTHON_INCLUDE_DIRS} )

  # Set up the Python module corresponding to this pyx file.
  get_target_property(_generated_files ${_pyx_target_name} generated_files)
  Python_add_library( ${_name} MODULE ${_generated_files} ${_other_module_sources} ${ARGN})

  # Force output to not be written to the Release or Debug subdirectory of the target
  # directory. The difference in build configuration should already be taken care of in
  # the CMAKE_CURRENT_BINARY_DIR on generators where that matters.
  set(_output_dir ${CMAKE_CURRENT_BINARY_DIR}/${_directories})
  set_target_properties(${_name} PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${_output_dir})
  foreach( _build_type RELEASE DEBUG RELWITHDEBINFO MINSIZEREL )
    set_target_properties(${_name} PROPERTIES LIBRARY_OUTPUT_DIRECTORY_${_build_type} ${_output_dir})
  endforeach(_build_type)

  set_target_properties(${_name} PROPERTIES OUTPUT_NAME ${_module_name})

  add_dependencies( ${_name} ${_pyx_target_name})
  target_link_libraries( ${_name} ${PYTHON_LIBRARIES} )

  # Remove internal variables' visibility to the user.
  foreach(_v _module_source _directories _module_name _generated_files _output_dir)
    set( ${_v} "" CACHE INTERNAL "" )
  endforeach(_v)
endfunction()

include( CMakeParseArguments )
