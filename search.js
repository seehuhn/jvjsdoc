goog.provide('jvjsdoc');

goog.require('goog.dom');
goog.require('goog.dom.classes');
goog.require('goog.events');
goog.require('goog.events.EventType');
goog.require('goog.ui.AutoComplete.Basic');
goog.require('goog.ui.AutoComplete.EventType');

/**
 * Initialise the javascript supported search box.
 */
jvjsdoc.enableSearch = function() {
    var search = goog.dom.getElement('search');
    var go = goog.dom.getElement('go');
    var xRef = window['jvXRef'];
    var baseDir = window['jvBaseDir'];

    var keys = [];
    for (var key in xRef) {
        keys.push(key);
    }

    var ac = new goog.ui.AutoComplete.Basic(keys, search, false);
    ac.setMaxMatches(20);
    goog.events.listen(ac, goog.ui.AutoComplete.EventType.UPDATE,
                       function(e) { go.click(); });
    goog.events.listen(search, goog.events.EventType.KEYDOWN,
                       function(e) {
                           if (e.keyCode == 13) {
                               setTimeout(function() {
                                   go.click();
                               }, 1);
                           }
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

    goog.events.listen(document.body, goog.events.EventType.KEYPRESS,
                       function(e) {
                           if (e.target != search &&
                               e.keyCode == goog.events.KeyCodes.F + 32) {
                               search.focus();
                               search.select();
                               e.preventDefault();
                           }
                       });

    goog.dom.classes.remove(search.parentElement, 'off');
};

/**
 * Allow to un-hide information about protected and deprecated methods.
 */
jvjsdoc.enableHiddenContent = function() {
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
jvjsdoc.init = function() {
    jvjsdoc.enableSearch();
    jvjsdoc.enableHiddenContent();
};

goog.exportSymbol('init', jvjsdoc.init);
