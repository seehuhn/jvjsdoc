goog.provide('jv');

goog.require('goog.dom');
goog.require('goog.dom.classes');
goog.require('goog.events');
goog.require('goog.events.EventType');
goog.require('goog.ui.AutoComplete.Basic');

/**
 * Initialise the javascript supported search box.
 */
jv.init = function() {
    var search = goog.dom.getElement('search');
    var go = goog.dom.getElement('go');
    var xRef = window['jvXRef'];
    var baseDir = window['jvBaseDir'];

    var keys = [];
    for (var key in xRef) {
        keys.push(key);
    }

    var ac = new goog.ui.AutoComplete.Basic(keys, search, false);
    goog.events.listen(search, goog.events.EventType.KEYDOWN,
                       function(e) {
                           setTimeout(function() {
                               if (e.keyCode == 13) go.click();
                           }, 1);
                       });

    goog.events.listen(go, goog.events.EventType.CLICK,
                       function(e) {
                           var key = search.value;
                           var next = xRef[key];
                           if (next) {
                               window.location.href = baseDir + '/' + next;
                           } else {
                               alert('unknown symbol ' + key);
                           }
                           return true;
                       });

    goog.dom.classes.remove(search.parentElement, 'off');
};

goog.exportSymbol('init', jv.init);
