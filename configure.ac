dnl Process this file with autoconf to produce a configure script.
dnl Copyright 2008, 2009  Jochen Voss

AC_INIT(jvjsdoc, 0.5, voss@seehuhn.de)
AM_INIT_AUTOMAKE

dnl Python support
AM_PATH_PYTHON

dnl Google closure library
AC_ARG_WITH([closure-library],
  [AS_HELP_STRING([--with-closure-library=DIR],
    [Give the location of the closure library source
     (DIR should be the directory which contains "closure/goog/deps.js"
     and "closure/bin/build/").])],
  [], [])
CLOSURE_LIBRARY=
CLOSURE_BASE=
CLOSURE_DEPSWRITER=
CLOSURE_BUILDER=
AS_IF([test "x$with_closure_library" != x ],
  [ AC_MSG_CHECKING([for the closure library source])
    jvtmpa="$with_closure_library/closure/goog/deps.js"
    jvtmpb="$with_closure_library/closure/bin/build"
    if ! test -f "$jvtmpa"; then
      AC_MSG_FAILURE([file "$jvtmpa" not found])
    elif ! test -d "$jvtmpb"; then
      AC_MSG_FAILURE([build tools directory "$jvtmpb" not found])
    else
      AC_SUBST([CLOSURE_LIBRARY], [`cd $with_closure_library && pwd`])
      AC_SUBST([CLOSURE_BASE], [$CLOSURE_LIBRARY/closure/goog])
      AC_SUBST([CLOSURE_DEPSWRITER],
               [$CLOSURE_LIBRARY/closure/bin/build/depswriter.py])
      AC_SUBST([CLOSURE_BUILDER],
               [$CLOSURE_LIBRARY/closure/bin/build/closurebuilder.py])
      AC_MSG_RESULT([$CLOSURE_LIBRARY])
    fi
  ])

dnl Google closure compiler
AC_ARG_WITH([closure-compiler],
  [AS_HELP_STRING([--with-closure-compiler=DIR],
    [Give the location of the closure compiler (the compiler.jar file).])],
  [], [])
CLOSURE_COMPILER=
AS_IF([test "x$with_closure_compiler" != x ],
  [ AC_MSG_CHECKING([for the closure compiler])
    if ! test -f "$with_closure_compiler"; then
      AC_MSG_FAILURE([file "$with_closure_compiler" not found])
    else
      AC_SUBST([CLOSURE_COMPILER], [$with_closure_compiler])
      AC_MSG_RESULT([$CLOSURE_COMPILER])
    fi
  ])

AC_CONFIG_FILES([Makefile])
AC_OUTPUT
