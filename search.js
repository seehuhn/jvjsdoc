goog.provide('jv');

goog.require('goog.dom');
goog.require('goog.dom.classes');
goog.require('goog.events');
goog.require('goog.events.EventType');
goog.require('goog.ui.AutoComplete.Basic');

/**
 * Initialise the javascript supported search box.
 */
jv.enableSearch = function() {
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

/**
 * Enable to un-hide information about protected and deprecated methods.
 */
jv.enableHiddenContent = function() {
    var hidden = goog.dom.getElementsByClass('hidden');
    function helper(elem, e) {
        goog.dom.classes.toggle(elem, 'hidden');
    };
    for (var i = 0; i < hidden.length; ++i) {
        var elem = hidden[i];
        var trigger = elem.firstChild;
        goog.events.listen(trigger, goog.events.EventType.CLICK,
                           goog.bind(helper, undefined, elem));
    }
};

/**
 * Initialise our javascript helpers.
 */
jv.init = function() {
    jv.enableSearch();
    jv.enableHiddenContent();
};

goog.exportSymbol('init', jv.init);
