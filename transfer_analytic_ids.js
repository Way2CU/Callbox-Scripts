/**
 * Google Analytics Integration Script
 *
 * This script will find all Google Analytic ids and transfer them to the
 * webhook call and allow multiple events to be fired.
 *
 * Copyright (c) 2014. by Way2CU, http://way2cu.com
 * Authors: Mladen Mijatov
 */
window.addEventListener('load', function(event) {
	window.__ctm_cvars = window.__ctm_cvars || [];
	var id_list = [];
	var regexp = /['"](UA-[\w]{6,}-\d+)['"]/;
	var scripts = document.getElementsByTagName('script');

	// parse scripts
	for (var i=0, count=scripts.length; i<count; i++) {
		var script = scripts[i];

		// make sure script is not external
		if (script.hasAttribute('src'))
			continue;

		// try to match analytics id
		var matches = script.innerHTML.match(regexp);
		if (matches !== null)
			id_list.push(matches[1]);
	}

	// push analytic ids
	if (id_list.length > 0)
		window.__ctm_cvars.push({'analytics_id_list': id_list});
}, false);
