ALL = search.js

DEBUG=0

ifeq ($(DEBUG),0)
JSFLAGS=--define=goog.DEBUG=false --compilation_level=ADVANCED_OPTIMIZATIONS
else
JSFLAGS=--compilation_level=SIMPLE_OPTIMIZATIONS --formatting=PRETTY_PRINT
endif

CLOSURE_LIBRARY = $(HOME)/project/s3/js/closure-library
CLOSURE_DEPSWRITER = $(CLOSURE_LIBRARY)/closure/bin/build/depswriter.py
CLOSURE_BUILDER = $(CLOSURE_LIBRARY)/closure/bin/build/closurebuilder.py
CLOSURE_COMPILER = $(HOME)/project/s3/js/compiler.jar

.PHONY: default
default: deps.js jsdoc.js

deps.js: $(ALL)
	$(CLOSURE_DEPSWRITER) \
	    --root_with_prefix=". `pwd`" \
	    --output_file=$@

jsdoc.js: $(ALL)
	$(CLOSURE_BUILDER) \
	    --root=$(CLOSURE_LIBRARY) \
	    --root=. \
	    --output_mode=compiled \
	    --compiler_jar=$(CLOSURE_COMPILER) \
	    --compiler_flags=--warning_level=VERBOSE \
	    --compiler_flags=--summary_detail_level=2 \
	    --compiler_flags=--js=$(CLOSURE_LIBRARY)/closure/goog/deps.js \
	    $(foreach f, $(JSFLAGS),--compiler_flags=$(f)) \
	    --namespace=jv \
	    --output_file=$@
	@echo ""
	chmod 644 $@

.PHONY: clean distclean
clean:
distclean: clean
	rm -f *~
