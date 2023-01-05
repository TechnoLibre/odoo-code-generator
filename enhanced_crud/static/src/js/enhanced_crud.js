odoo.define("enhanced_crud", function (require) {
    "use strict";

    /**
     * Imports and tranlations
     */
    let core = require("web.core"),
        qweb = core.qweb,
        _t = core._t,
        _lt = core._lt,
        t_4ECrudAdd = _lt("ECrudAdd"),
        t_4ECrudModify = _lt("ECrudModify"),
        t_4SingleDelete = _lt("Are you sure you want to delete this record?"),
        t_4MultiDelete = _lt("Are you sure you want to delete this records?"),
        t_4NoChangeMsg = _lt("You have not made any changes."),
        t_4ChangeOnPrevPagination = _lt(
            "Modifications have been made, do you want to save them before showing the previous element?"
        ),
        t_4ChangeOnNextPagination = _lt(
            "Modifications have been made, do you want to save them before showing the next element?"
        ),
        t_4ChangeOnCloseWindow = _lt("Modifications have been made, do you want to save them?"),
        t_4Warning = _lt("ECrudWarning"),
        t_4ECrudReports = _lt("ECrudReports"),
        t_4ECrudActions = _lt("ECrudActions"),
        t_4ECrudOthers = _lt("ECrudOthers"),
        t_4ECrudReloadNeeded = _lt("A page reload is needed, we will be back in a bit."),
        t_4SingleElementOption = _lt("(Single Element Option)"),
        ActionManager = require("web.ActionManager"),
        ListController = require("web.ListController"),
        KanbanController = require("web.KanbanController"),
        FormController = require("web.FormController"),
        ListRenderer = require("web.ListRenderer"),
        KanbanRenderer = require("web.KanbanRenderer"),
        ListView = require("web.ListView"),
        KanbanView = require("web.KanbanView"),
        FormView = require("web.FormView"),
        BasicModel = require("web.BasicModel"),
        viewRegistry = require("web.view_registry"),
        Dialog = require("web.Dialog"),
        Pager = require("web.Pager"),
        FieldOne2Many = require("web.relational_fields").FieldOne2Many,
        Context = require("web.Context"),
        pyUtils = require("web.py_utils"),
        FieldStatus = require("web.relational_fields").FieldStatus;

    /**
     * Function to obtain (recursively) a father from an element with a _window_disposition variable setted
     * @param element
     * @returns {*}
     * @private
     */
    function _get_parent_window_disposition(element) {
        if (element.getParent()) {
            let parent = element.getParent();
            if (parent._window_disposition === undefined) {
                return _get_parent_window_disposition(parent);
            } else {
                return parent;
            }
        } else {
            return null;
        }
    }

    /**
     * Same function as web.mixins -> OdooEvent
     * @param target
     * @param name
     * @param data
     * @constructor
     */
    function OdooEvent(target, name, data) {
        this.target = target;
        this.name = name;
        this.data = Object.create(null);
        _.extend(this.data, data);
        this.stopped = false;
    }

    OdooEvent.prototype.stopPropagation = function () {
        this.stopped = true;
    };

    OdooEvent.prototype.is_stopped = function () {
        return this.stopped;
    };

    FieldOne2Many.include({
        /**
         * Redefining the _openFormDialog method to take into account whether a parent with a _window_disposition
         * variable setted exists or not and proceed accordingly
         * @param params
         * @private
         */
        _openFormDialog: function (params) {
            let _enhanced_crud_form_controller = _get_parent_window_disposition(this);
            if (_enhanced_crud_form_controller) {
                // New behaviour
                let context = this.record.getContext(
                    _.extend({}, this.recordParams, {additionalContext: params.context})
                );
                let event = new OdooEvent(
                    this,
                    "open_one2many_record",
                    _.extend(params, {
                        domain: this.record.getDomain(this.recordParams),
                        context: context,
                        field: this.field,
                        fields_view: this.attrs.views && this.attrs.views.form,
                        parentID: this.value.id,
                        viewInfo: this.view,
                        deletable: this.activeActions.delete,
                    })
                );

                _enhanced_crud_form_controller._onOpenOne2ManyRecord(event);
            } else {
                // Default behaviour
                this._super.apply(this, arguments);
            }
        },
    });

    /**
     * Function to obtain the Action Manager from a element
     * @param self
     * @private
     */
    function _enhanced_crud_findActionManager(self) {
        return (
            self.findAncestor(function (a) {
                return a instanceof ActionManager;
            }) || null
        );
    }

    /**
     * Function to obtain the current controller (list or kanban) widget from the Action Manager
     * @param self
     * @private
     */
    function _enhanced_crud_findCurrentControllerWidget(self) {
        let am = _enhanced_crud_findActionManager(self);
        if (am) {
            let currentController = am.getCurrentController();
            if (currentController) {
                return currentController.widget;
            }
        }
        return null;
    }

    FieldStatus.include({
        /**
         * Redefining the _setValue method to take into account whether a parent with a _window_disposition
         * variable setted exists or not and proceed accordingly
         * @param value
         * @param options
         * @returns {*}
         * @private
         */
        _setValue: function (value, options) {
            let _enhanced_crud_form_controller = _get_parent_window_disposition(this);
            if (_enhanced_crud_form_controller) {
                if (this.lastSetValue === value || (this.value === false && value === "")) {
                    return $.when();
                }
                this.lastSetValue = value;
                try {
                    value = this._parseValue(value);
                    this._isValid = true;
                } catch (e) {
                    this._isValid = false;
                    this.trigger_up("set_dirty", {dataPointID: this.dataPointID});
                    return $.Deferred().reject();
                }
                if (!(options && options.forceChange) && this._isSameValue(value)) {
                    return $.when();
                }
                let def = $.Deferred(),
                    changes = {};
                changes[this.name] = value;

                // New behaviour
                let event = new OdooEvent(this, "field_changed", {
                    dataPointID: this.dataPointID,
                    changes: changes,
                    viewType: this.viewType,
                    doNotSetDirty: options && options.doNotSetDirty,
                    notifyChange: !options || options.notifyChange !== false,
                    allowWarning: options && options.allowWarning,
                    onSuccess: def.resolve.bind(def),
                    onFailure: def.reject.bind(def),
                    force_save: true,
                });
                _enhanced_crud_form_controller._onFieldChanged(event);

                return def;
            } else {
                this._super.apply(this, arguments); // Default behaviour
            }
        },
    });

    ActionManager.include({
        _reload_and_open: true,

        _views_toolbars: {},

        /**
         * Redefining the _onExecuteAction method to take into account whether a parent with a _window_disposition
         * variable setted exists or not and proceed accordingly
         * @param ev
         * @private
         */
        _onExecuteAction: function (ev) {
            let currentController = this.getCurrentController(),
                currentControllerWidget = currentController.widget;
            if (!currentControllerWidget._window_disposition || currentControllerWidget._window_disposition !== "new") {
                this._super.apply(this, arguments);
            } else {
                ev.stopPropagation();
                let self = this,
                    actionData = ev.data.action_data,
                    env = ev.data.env,
                    context = new Context(env.context, actionData.context || {}),
                    activeID = "active_id" in env.context && env.context["active_id"],
                    recordID = env.currentID || activeID, // pyUtils handles null value, not undefined
                    def = $.Deferred(),
                    reload_and_open = (noOpen) => {
                        currentControllerWidget._enhanced_crud_reload().then(() => {
                            if (recordID && !noOpen) {
                                currentControllerWidget._enhanced_crud_generic_actionwindow(recordID, t_4ECrudModify);
                            }
                        });
                    };

                if (actionData.special) {
                    def = $.when({type: "ir.actions.act_window_close", infos: "special"});
                } else if (actionData.type === "object") {
                    let args = recordID ? [[recordID]] : [env.resIDs];
                    if (actionData.args) {
                        try {
                            let additionalArgs = JSON.parse(actionData.args.replace(/'/g, '"'));
                            args = args.concat(additionalArgs);
                        } catch (e) {
                            console.error("Could not JSON.parse arguments", actionData.args);
                        }
                    }
                    args.push(context.eval());
                    def = this._rpc({
                        route: "/web/dataset/call_button",
                        params: {
                            args: args,
                            method: actionData.name,
                            model: env.model,
                        },
                    });
                } else if (actionData.type === "action") {
                    def = this._loadAction(
                        actionData.name,
                        _.extend(pyUtils.eval("context", context), {
                            active_model: env.model,
                            active_ids: env.resIDs,
                            active_id: recordID,
                        })
                    );
                }

                def.fail(ev.data.on_fail);
                this.dp.add(def).then(function (action) {
                    let effect = false;
                    if (actionData.effect) {
                        effect = pyUtils.py_eval(actionData.effect);
                    }

                    if (action && action.constructor === Object) {
                        let ctx = new Context(
                            _.object(
                                _.reject(_.pairs(env.context), function (pair) {
                                    return (
                                        pair[0].match(
                                            "^(?:(?:default_|search_default_|show_).+|" +
                                                ".+_view_ref|group_by|group_by_no_leaf|active_id|" +
                                                "active_ids|orderedBy)$"
                                        ) !== null
                                    );
                                })
                            )
                        );
                        ctx.add(actionData.context || {});
                        ctx.add({active_model: env.model});
                        if (recordID) {
                            ctx.add({
                                active_id: recordID,
                                active_ids: [recordID],
                            });
                        }
                        ctx.add(action.context || {});
                        action.context = ctx;
                        action.effect = effect || action.effect;

                        let options = {on_close: ev.data.on_closed},
                            doAction = self.doAction(action, options).then(ev.data.on_success, ev.data.on_fail);

                        doAction.then(function (response) {
                            if (response.type === "ir.actions.act_window_close") {
                                reload_and_open(self._reload_and_open);
                                self._reload_and_open = true;
                            } else {
                                self._reload_and_open = false;
                            }

                            if (Object.keys(self.controllers).length >= 2 && recordID) {
                                self._rpc({
                                    model: currentControllerWidget.modelName,
                                    method: "read",
                                    args: [[recordID], ["display_name"]],
                                }).then(function (readed) {
                                    let breadcrumbs = self._getBreadcrumbs();
                                    breadcrumbs.splice(
                                        1,
                                        1,
                                        {
                                            controllerID: currentController.jsID + "-recordID:" + recordID.toString(),
                                            title: readed[0]["display_name"],
                                        },
                                        breadcrumbs[breadcrumbs.length - 1]
                                    );
                                    self.controlPanel.update({breadcrumbs: breadcrumbs}, {clear: false});
                                });
                            }
                        });
                        currentControllerWidget._toggleDisabled4ClickableButtons();
                        return doAction;
                    } else if (recordID) {
                        return reload_and_open();
                    }
                });
            }
        },

        /**
         * Redefining the _onBreadcrumbClicked method to take into account whether a controllerID with an Enhanced CRUD
         * module special notation (ej: controller_19-recordID:1) exists or not and proceed accordingly
         * @param ev
         * @private
         */
        _onBreadcrumbClicked: function (ev) {
            ev.stopPropagation();
            let data = ev.data.controllerID;
            if (data.indexOf("-") !== -1) {
                let splitted = data.split("-"),
                    controllerID = splitted[0],
                    recordData = splitted[1].split(":"),
                    recordID = recordData[1];

                return this._restoreController(controllerID).then(() => {
                    this.getCurrentController().widget._enhanced_crud_generic_actionwindow(
                        parseInt(recordID),
                        t_4ECrudModify
                    );
                });
            } else {
                this._restoreController(ev.data.controllerID); // Default behaviour
            }
        },

        /**
         * Redefining the loadViews method to obtain the toolbar option for the different views to be used later in the
         * context menu
         */
        loadViews: function () {
            let self = this,
                def = self._super.apply(self, arguments);
            def.then((response) => {
                for (let i in response) {
                    if (["kanban", "list", "form"].indexOf(i) !== -1 && response[i].toolbar) {
                        self._views_toolbars[i] = response[i].toolbar;
                    }
                }
            });
            return def;
        },
    });

    /**
     * Util function to destroy an existence Context Menu
     * @param attrs
     * @param js_class_value
     * @private
     */
    function _enhanced_crud_destroyContextMenu(attrs, js_class_value) {
        let js_class_in = "js_class" in attrs;
        if (!js_class_in || (js_class_in && attrs["js_class"] !== js_class_value)) {
            if ($.contextMenu) {
                $.contextMenu("destroy", {context: this});
            }
        }
    }

    /**
     * Redefining the init methods of List and Kanban Renderers in order to destroy the Context Menu
     * The Context Menu created in the Enhanced CRUD List and Kanban Renderer must be destroy for the regular List and Kanban Renderers
     */
    ListRenderer.include({
        init: function () {
            this._super.apply(this, arguments);
            _enhanced_crud_destroyContextMenu(this.arch.attrs, "enhanced_crud_tree");
        },
    });
    KanbanRenderer.include({
        init: function () {
            this._super.apply(this, arguments);
            _enhanced_crud_destroyContextMenu(this.arch.attrs, "enhanced_crud_kanban");
        },
    });

    /**
     * Enhanced CRUD Pager
     */
    let EnhancedCrudPager = Pager.extend({
        /**
         * Redefining the init method to enable / disable the can_edit option
         */
        init: function () {
            let self = this;
            self._super.apply(self, arguments);
            self._rpc({
                model: "base",
                method: "enhanced_crud_can_edit_pager",
            }).then(
                function (response) {
                    self.options.can_edit = response === "True";
                },
                function () {
                    self.options.can_edit = false;
                }
            );
        },

        template: "EnhancedCrud.pager",

        events: _.extend({}, Pager.prototype.events, {
            "click .o_enhanced_crud_pager_previous": "_onPrevious",
            "click .o_enhanced_crud_pager_next": "_onNext",
            "click .o_enhanced_crud_pager_first": "_onFirst",
            "click .o_enhanced_crud_pager_last": "_onLast",
            "click .o_enhanced_crud_pager_reload": "_onReload",
            "change .o_enhanced_crud_pagination": "_onPagination",
        }),

        /**
         * Function to obtain the current_min from the pager
         * @returns {number}
         * @private
         */
        _get_final_current_min: function () {
            return this.state.size - (this.state.size % this.state.limit || this.state.limit) + 1;
        },

        /**
         * Replacing the _updateArrows method to take into account the new buttons
         * @private
         */
        _updateArrows: function () {
            if (this.state.current_min === 1) {
                if (this.state.current_min === this._get_final_current_min()) {
                    this.$("button").prop("disabled", true);
                } else {
                    this.$("button.o_enhanced_crud_pager_previous").prop("disabled", true);
                    this.$("button.o_enhanced_crud_pager_first").prop("disabled", true);
                    this.$("button.o_enhanced_crud_pager_next").prop("disabled", false);
                    this.$("button.o_enhanced_crud_pager_last").prop("disabled", false);
                }
            } else if (this.state.current_min === this._get_final_current_min()) {
                this.$("button.o_enhanced_crud_pager_previous").prop("disabled", false);
                this.$("button.o_enhanced_crud_pager_first").prop("disabled", false);
                this.$("button.o_enhanced_crud_pager_next").prop("disabled", true);
                this.$("button.o_enhanced_crud_pager_last").prop("disabled", true);
            } else {
                this.$("button.o_enhanced_crud_pager_previous").prop("disabled", false);
                this.$("button.o_enhanced_crud_pager_first").prop("disabled", false);
                this.$("button.o_enhanced_crud_pager_next").prop("disabled", false);
                this.$("button.o_enhanced_crud_pager_last").prop("disabled", false);
            }

            this.$("button.o_enhanced_crud_pager_reload").prop("disabled", false);
            this.$("select.o_enhanced_crud_pagination")[0].value = this.state.limit;
        },

        /**
         * Common function for the page_changed trigger
         * @param current_min
         * @param limit
         * @private
         */
        trigger_pager_changed: function (current_min, limit) {
            let self = this,
                currentControllerWidget = _enhanced_crud_findCurrentControllerWidget(self);
            return self.options
                .validate()
                .then(function () {
                    if (current_min) {
                        self.state.current_min = current_min;
                    }
                    if (limit) {
                        self.state.limit = limit;
                    }
                    self._render();
                    self.trigger("pager_changed", _.clone(self.state));
                    return self.state;
                })
                .then(() => {
                    if (currentControllerWidget.viewType === "list") {
                        currentControllerWidget._toggleDisabled4ClickableButtons();
                    }
                });
        },

        /**
         * Function to go to the first page
         * @param event
         * @private
         */
        _onFirst: function (event) {
            this.trigger_pager_changed(1);
        },

        /**
         * Function to go to the last page
         * @param event
         * @private
         */
        _onLast: function (event) {
            this.trigger_pager_changed(this._get_final_current_min());
        },

        /**
         * Function to go to reload the grid
         * @param event
         * @private
         */
        _onReload: function (event) {
            this.trigger_pager_changed();
        },

        /**
         * Function to execute a pagination page by page
         * @param event
         * @private
         */
        _onPagination: function (event) {
            this.trigger_pager_changed(1, parseInt(event.currentTarget.value));
        },
    });

    /**
     * Common stuffs for Enhanced CRUD List and Form Controllers
     * @type {{_window_disposition: null, init: init, renderPager: renderPager, _enhanced_crud_generic_actionwindow: _enhanced_crud_generic_actionwindow, _enhanced_crud_action_window_close: (function(): *), _enhanced_crud_window_disposition: (function(): (*|Promise))}}
     */
    let EnhancedCrudCommonController = {
        _window_disposition: null,

        /**
         * Replacing the renderPager in order to used the EnhancedCrudPager
         * @param $node
         * @param options
         */
        renderPager: function ($node, options) {
            let data = this.model.get(this.handle, {raw: true});
            this.pager = new EnhancedCrudPager(this, data.count, data.offset + 1, data.limit, options);

            this.pager.on("pager_changed", this, function (newState) {
                let self = this;
                this.pager.disable();
                data = this.model.get(this.handle, {raw: true});
                let limitChanged = data.limit !== newState.limit;
                this.reload({limit: newState.limit, offset: newState.current_min - 1})
                    .then(function () {
                        // Reset the scroll position to the top on page changed only
                        if (!limitChanged) {
                            self.trigger_up("scrollTo", {top: 0});
                        }
                    })
                    .then(this.pager.enable.bind(this.pager));
            });
            this.pager.appendTo($node);
            this._updatePager(); // to force proper visibility
        },

        /**
         * Function to generate the action window of the 'New Window' option of the window disposition configuration variable
         * @param record_id
         * @param action_name
         * @param prev
         * @param nextone
         * @private
         */
        _enhanced_crud_generic_actionwindow: function (
            record_id = null,
            action_name = t_4ECrudAdd,
            prev = null,
            nextone = null
        ) {
            let self = this,
                form_view = self.actionViews.filter((aView) => aView.type === "form"),
                form_view_id = form_view[0].fieldsView.view_id,
                additional_context = {additional_context: {set_js_class_4view: true}};

            let action = {
                type: "ir.actions.act_window",
                name: action_name,
                res_model: self.modelName,
                view_type: "form",
                view_mode: "form",
                views: [[form_view_id, "form"]],
                view_id: form_view_id,
                target: "new",
            };

            let currentControllerWidget = _enhanced_crud_findCurrentControllerWidget(self);

            if (record_id) {
                if (prev || nextone) {
                    let currentControllerState = currentControllerWidget.model.get(currentControllerWidget.handle, {
                            raw: true,
                        }),
                        indexOf = currentControllerState.res_ids.indexOf(record_id);

                    if (prev && indexOf - 1 >= 0) {
                        record_id = currentControllerState.res_ids[indexOf - 1];
                    } else if (nextone && indexOf + 1 <= currentControllerState.res_ids.length) {
                        record_id = currentControllerState.res_ids[indexOf + 1];
                    }
                }

                action["res_id"] = record_id;
                if (action_name === t_4ECrudAdd) {
                    additional_context["additional_context"]["enhanced_crud_copying"] = true;
                }
            }

            self.do_action(action, additional_context).then(() => {
                let am = _enhanced_crud_findActionManager(currentControllerWidget),
                    breadcrumbs = am._getBreadcrumbs(),
                    controllerInDialogWidget = am.currentDialogController.widget,
                    state4ControllerInDialogWidget = controllerInDialogWidget.model.get(
                        controllerInDialogWidget.handle
                    );
                breadcrumbs.push({
                    controllerID: controllerInDialogWidget.jsID,
                    title: record_id ? state4ControllerInDialogWidget.data.display_name : _t("New"),
                });
                am.controlPanel.update({breadcrumbs: breadcrumbs}, {clear: false});
            });
        },

        /**
         * Function to close the action window of the 'New Window' option of the window disposition configuration variable
         * @returns {*}
         * @private
         */
        _enhanced_crud_action_window_close: function () {
            $("div.modal").modal("hide");
        },

        /**
         * Function to obtain the value for the window disposition configuration variable
         * @returns {Promise<T | never>}
         */
        _enhanced_crud_window_disposition: function () {
            let self = this;
            return self._rpc({
                model: self.modelName,
                method: "enhanced_crud_window_disposition",
            });
        },

        /**
         * Function to trigger the reload action
         * @private
         */
        _enhanced_crud_reload: function () {
            return this.reload();
        },

        /**
         * Same function as web.Sidebar -> _onItemActionClicked
         * @param action
         * @param kanbanRecordID
         * @private
         */
        _onSideBarItemActionClick: function (action, kanbanRecordID) {
            let self = this,
                env = self._getSidebarEnv(),
                state = this.model.get(this.handle);
            if (kanbanRecordID) {
                env.activeIds = [kanbanRecordID];
            }
            env = _.extend(env, {domain: state.getDomain()});
            let activeIdsContext = {
                active_id: env.activeIds[0],
                active_ids: env.activeIds,
                active_model: env.model,
                active_domain: env.domain,
            };
            let context = pyUtils.eval("context", new Context(env.context, activeIdsContext));

            self._rpc({
                route: "/web/action/load",
                params: {action_id: action.id, context: context},
            }).done(function (result) {
                result.context = new Context(result.context || {}, activeIdsContext).set_eval_context(context);
                result.flags = result.flags || {};
                result.flags.new_window = true;
                self.do_action(result, {
                    on_close: function () {
                        self._enhanced_crud_reload();
                    },
                });
            });
        },
    };

    /**
     * Enhanced CRUD List Controller
     */
    let EnhancedCrudListController = ListController.extend(
        _.extend(EnhancedCrudCommonController, {
            buttons_template: "EnhancedCrudList.buttons",

            /**
             * Redefining the init method to call the _enhanced_crud_window_disposition method just one time
             */
            init: function () {
                let self = this;
                self._super.apply(self, arguments);
                self.hasSidebar = false;
                self._enhanced_crud_window_disposition().then(function (response) {
                    self._window_disposition = response;
                });
            },

            /**
             * Replacing the _onOpenRecord method to take into account the 'Current Window' option of the window disposition configuration variable
             * @param event
             * @private
             */
            _onOpenRecord: function (event) {
                let self = this;
                event.stopPropagation();
                let record = self.model.get(event.data.id, {raw: true});
                self.trigger_up("switch_view", {
                    view_type: "form",
                    res_id: record.res_id,
                    mode: "edit",
                    model: self.modelName,
                });
            },

            /**
             * Replacing the _onCreateRecord method to take into account the 'Current Window' option of the window disposition configuration variable
             * @param event
             * @private
             */
            _onCreateRecord: function (event) {
                let self = this;
                if (event) {
                    event.stopPropagation();
                }
                let state = self.model.get(self.handle, {raw: true});
                if (self.editable && !state.groupedBy.length) {
                    self._addRecord();
                } else {
                    self.trigger_up("switch_view", {view_type: "form", res_id: undefined});
                }
            },

            /**
             * Function to obtain the selected element in a grid when modifying
             * @param event
             * @returns {*}
             * @private
             */
            _enhanced_crud_get_current_id: function (event) {
                let self = this,
                    record = self.model.get(event.data.id, {raw: true});
                return record ? record.res_id : null;
            },

            custom_events: _.extend({}, ListController.prototype.custom_events, {
                /**
                 * Replacing the open_record method to take into account the option of the window disposition configuration variable
                 * @param event
                 */
                open_record: function (event) {
                    let self = this;
                    if (self._window_disposition === "new") {
                        self._enhanced_crud_generic_actionwindow(
                            self._enhanced_crud_get_current_id(event),
                            t_4ECrudModify
                        );
                    } else if (self._window_disposition === "current") {
                        self._onOpenRecord(event);
                    }
                },
            }),

            /**
             * Replacing the _onToggleArchiveState mehtod in order to use the call result
             * @param archive
             * @returns {*}
             * @private
             */
            _onToggleArchiveState: function (archive) {
                return this._archive(this.selectedRecords, archive);
            },

            /**
             * Function to obtain the Other actions having the hasSideBar variable setted to false
             * @private
             */
            _get_other_actions: function () {
                let self = this,
                    other = [{label: _t("Export"), callback: self._onExportData.bind(self)}],
                    reload = () => {
                        self._enhanced_crud_reload();
                    };
                if (self.archiveEnabled) {
                    other.push({
                        label: _t("Archive"),
                        callback: function () {
                            Dialog.confirm(
                                self,
                                _t("Are you sure that you want to archive all the selected records?"),
                                {
                                    confirm_callback: () => {
                                        self._onToggleArchiveState(true).then(reload);
                                    },
                                }
                            );
                        },
                    });
                    other.push({
                        label: _t("Unarchive"),
                        callback: () => {
                            self._onToggleArchiveState(false).then(reload);
                        },
                    });
                }
                return other;
            },

            /**
             * Function to create html elements (in the case of buttons with onclick setted)
             * @param textNode
             * @param callback
             * @param element
             * @param className
             * @returns {HTMLElement}
             * @private
             */
            _get_element: function (textNode, callback, element, className) {
                element = element || "button";
                let element_is_button = element === "button";
                className = className || "dropdown-item";
                element = document.createElement(element);
                element.classList.add(className);
                if (element_is_button) {
                    element.onclick = callback;
                }
                if (textNode) {
                    element.appendChild(document.createTextNode(textNode));
                }
                return element;
            },

            /**
             * Function to fill the More option menu
             * @param just_return
             * @returns {Array}
             */
            set_more_menu: function (just_return) {
                let self = this,
                    l_menu = [],
                    menu = self.$buttons.find("div.dropdown-menu"),
                    print_len = self.toolbarActions.print.length,
                    action_len = self.toolbarActions.action.length,
                    other = self._get_other_actions();

                if (print_len) {
                    l_menu.push([t_4ECrudReports, []]);
                    if (!just_return) {
                        menu[0].appendChild(self._get_element(t_4ECrudReports, null, "span", "dropdown-item-text"));
                    }
                    self.toolbarActions.print.forEach(function (action) {
                        l_menu[l_menu.length - 1][1].push([
                            action.name,
                            () => {
                                self._onSideBarItemActionClick(action);
                            },
                        ]);
                        if (!just_return) {
                            menu[0].appendChild(
                                self._get_element(action.name, () => {
                                    self._onSideBarItemActionClick(action);
                                })
                            );
                        }
                    });
                }

                if (action_len) {
                    if (print_len && !just_return) {
                        menu[0].appendChild(self._get_element(null, null, "div", "dropdown-divider"));
                    }
                    l_menu.push([t_4ECrudActions, []]);
                    if (!just_return) {
                        menu[0].appendChild(self._get_element(t_4ECrudActions, null, "span", "dropdown-item-text"));
                    }
                    self.toolbarActions.action.forEach(function (action) {
                        l_menu[l_menu.length - 1][1].push([
                            action.name,
                            () => {
                                self._onSideBarItemActionClick(action);
                            },
                        ]);
                        if (!just_return) {
                            menu[0].appendChild(
                                self._get_element(action.name, () => {
                                    self._onSideBarItemActionClick(action);
                                })
                            );
                        }
                    });
                }

                if (other.length) {
                    if ((print_len || action_len) && !just_return) {
                        menu[0].appendChild(self._get_element(null, null, "div", "dropdown-divider"));
                    }
                    l_menu.push([t_4ECrudOthers, []]);
                    if (!just_return) {
                        menu[0].appendChild(self._get_element(t_4ECrudOthers, null, "span", "dropdown-item-text"));
                    }
                    other.forEach(function (action) {
                        if (action.label !== _t("Delete")) {
                            l_menu[l_menu.length - 1][1].push([action.label, action.callback]);
                            if (!just_return) {
                                menu[0].appendChild(self._get_element(action.label, action.callback));
                            }
                        }
                    });

                    if ("duplicate" in self.activeActions && self.activeActions.duplicate) {
                        let duplicateAllThen = () => {
                            Promise.all(
                                _.map(self.getSelectedIds(), (selectedId) => {
                                    return self._rpc({
                                        model: self.modelName,
                                        method: "copy",
                                        context: self.model.get(self.handle).getContext(),
                                        args: [selectedId],
                                    });
                                })
                            ).then(function () {
                                self._enhanced_crud_reload();
                            });
                        };
                        l_menu[l_menu.length - 1][1].push([_lt("Duplicate"), duplicateAllThen]);
                        if (!just_return) {
                            menu[0].appendChild(self._get_element(_lt("Duplicate"), duplicateAllThen));
                        }
                    }
                }

                return l_menu;
            },

            /**
             * Replacing the renderButtons method to take into account the new buttons
             */
            renderButtons: function () {
                let self = this;
                self._super.apply(self, arguments);
                if (self.$buttons) {
                    self.$buttons.on("click", ".o_button_enhanced_crud_add", function (event) {
                        if (self._window_disposition === "new") {
                            self._enhanced_crud_generic_actionwindow();
                        } else if (self._window_disposition === "current") {
                            self._onCreateRecord(event);
                        }
                    });

                    self.$buttons.on("click", ".o_button_enhanced_crud_modify", function (event) {
                        if (self.selectedRecords.length) {
                            if (self._window_disposition === "new") {
                                self._enhanced_crud_generic_actionwindow(self.getSelectedIds()[0], t_4ECrudModify);
                            }
                        }
                    });

                    self.$buttons.on("click", ".o_button_enhanced_crud_delete", function (event) {
                        self._deleteRecords(self.selectedRecords);
                    });

                    setTimeout(function () {
                        self.set_more_menu();
                    });
                }
            },

            /**
             * Toggle the disabled class of buttons
             * @param selection
             * @private
             */
            _toggleDisabled4ClickableButtons: function (selection) {
                let self = this;
                selection = selection || [];
                self.$buttons
                    .find(".o_button_enhanced_crud_1click2enable")
                    .toggleClass("disabled", !selection.length || selection.length > 1);
                self.$buttons.find(".o_button_enhanced_crud_xclick2enable").toggleClass("disabled", !selection.length);
            },

            /**
             * Redefining the _onSelectionChanged to be able to toggle the disabled class of the new buttons
             * @param event
             */
            _onSelectionChanged: function (event) {
                let self = this;
                self._super.apply(self, arguments);
                self._toggleDisabled4ClickableButtons(event.data.selection);
            },

            /**
             * Replacing the _deleteRecords to take into account the confirmation messages
             * @param ids
             * @private
             */
            _deleteRecords: function (ids) {
                let self = this;

                function doIt() {
                    return self.model
                        .deleteRecords(ids, self.modelName)
                        .then(self._onDeletedRecords.bind(self, ids))
                        .then(function () {
                            self._toggleDisabled4ClickableButtons();
                        });
                }

                if (this.confirmOnDelete) {
                    Dialog.confirm(this, ids.length > 1 ? t_4MultiDelete : t_4SingleDelete, {confirm_callback: doIt});
                } else {
                    doIt();
                }
            },

            /**
             * Function to unselect rows "manually"
             */
            _unSelectRows: function () {
                if (this.viewType === "list") {
                    this.renderer._unSelectRows();
                    this._toggleDisabled4ClickableButtons();
                }
            },

            /**
             * Replacing the function to trigger the reload action in order to do specific things for the list controller
             * @private
             */
            _enhanced_crud_reload: function () {
                let self = this;
                return self.reload().then(self._unSelectRows.bind(self));
            },
        })
    );

    /**
     * Enhanced CRUD List Renderer
     * Now with one click we will just select the row and with a double click we will trigger the open_record event
     * + Context Menu
     */
    let EnhancedCrudListRendererEvents = _.clone(ListRenderer.prototype.events);
    EnhancedCrudListRendererEvents["click tbody tr"] = "_onSelectRecord";
    EnhancedCrudListRendererEvents["dblclick tbody tr"] = "_onRowClicked";
    let EnhancedCrudListRenderer = ListRenderer.extend({
        events: EnhancedCrudListRendererEvents,

        init: function (parent, state, params) {
            let self = this;
            self._super.apply(self, arguments);

            self._rpc({
                model: self.state.model,
                method: "enhanced_crud_contextmenu",
            }).then(function (response) {
                if (response === "True") {
                    $.contextMenu({
                        selector: "tbody tr",
                        build: function ($trigger, e) {
                            let listControllerWidget = parent.getCurrentController().widget,
                                listState = listControllerWidget.model.get(listControllerWidget.handle, {raw: true}),
                                l_menu = listControllerWidget.set_more_menu(true),
                                d_callbacks = {},
                                items = {},
                                atleastone = false;

                            for (let i in params.activeActions) {
                                if (params.activeActions[i]) {
                                    atleastone = true;
                                    if (i === "edit") {
                                        items["modify"] = {
                                            name: t_4ECrudModify + " " + t_4SingleElementOption,
                                            icon: "edit",
                                        };
                                    } else if (i === "delete") {
                                        items["delete"] = {name: _lt("ECrudDelete"), icon: "delete"};
                                    }
                                }
                            }

                            if ("form" in parent._views_toolbars) {
                                let relate = parent._views_toolbars["form"]["relate"];
                                if (relate.length) {
                                    items["sep" + l_menu.length] = "---------";
                                }
                                for (let i in relate) {
                                    items[relate[i].name] = {name: relate[i].name + " " + t_4SingleElementOption};
                                    d_callbacks[relate[i].name] = () => {
                                        listControllerWidget._onSideBarItemActionClick(relate[i]);
                                    };
                                }
                            }

                            l_menu.forEach((menu, index) => {
                                if (atleastone) {
                                    items["sep" + index] = "---------";
                                }
                                let submenus = {};
                                menu[1].forEach((submenu) => {
                                    submenus[submenu[0]] = {name: submenu[0]};
                                    d_callbacks[submenu[0]] = submenu[1];
                                });
                                items["fold" + index] = {
                                    name: menu[0],
                                    items: submenus,
                                };
                            });

                            return {
                                items: items,
                                callback: function (key, options) {
                                    if (key === "modify") {
                                        listControllerWidget.trigger_up("open_record", {
                                            id: options.$trigger.data("id"),
                                            target: options.$trigger,
                                        });
                                    } else if (key === "delete") {
                                        let selectedStringIds = self._getSelectedStringIds();

                                        if (!selectedStringIds.length) {
                                            // Just in case...
                                            Dialog.alert(self, t_4ECrudReloadNeeded, {
                                                confirm_callback: () => {
                                                    parent.do_action("reload");
                                                },
                                            });
                                        }

                                        let selectedData = _.filter(listState.data, (e) => {
                                                return selectedStringIds.indexOf(e.id) !== -1;
                                            }),
                                            selectedIds = _.map(selectedData, (e) => {
                                                return e.data.id;
                                            });

                                        Dialog.confirm(
                                            self,
                                            selectedData.length > 1 ? t_4MultiDelete : t_4SingleDelete,
                                            {
                                                confirm_callback: () => {
                                                    listControllerWidget
                                                        ._rpc({
                                                            model: listState.model,
                                                            method: "unlink",
                                                            context: listState.getContext(),
                                                            args: [selectedIds],
                                                        })
                                                        .then(function () {
                                                            listControllerWidget._enhanced_crud_reload();
                                                        });
                                                },
                                            }
                                        );
                                    } else {
                                        d_callbacks[key]();
                                    }
                                },
                            };
                        },
                        events: {
                            show: function (options) {
                                self._innerOnSelectRecord(options.$trigger);
                            },
                        },
                    });
                }
            });
        },

        /**
         * Util function for _onSelectRecord redefinition
         * @param target
         * @param changeSelection
         * @private
         */
        _innerOnSelectRecord: function (target, changeSelection) {
            if (!$(target).hasClass("o_list_record_selector")) {
                changeSelection = changeSelection || false;
                let record_selector_input = $(target).find("div:not(.o_field_boolean) input:first");
                let checked = record_selector_input.prop("checked");
                let selection = $("tbody .o_list_record_selector input:checked");
                if (changeSelection && !checked && selection.length) {
                    selection.prop("checked", false);
                    selection.closest("tr").css("background-color", "#f5f5f5");
                } else {
                    $("tbody tr").css("background-color", "#f5f5f5");
                }
                if (changeSelection) {
                    record_selector_input.prop("checked", !checked);
                } else {
                    record_selector_input.prop("checked", true);
                }
                $(target).css("background-color", "#CCC");
                this._updateSelection();
                return true;
            }
            return false;
        },

        /**
         * Redefining the _onSelectRecord method, now with one click we just select the row and with a double click we
         * trigger the open_record event
         * @param event
         * @private
         */
        _onSelectRecord: function (event) {
            event.stopPropagation();
            if (!this._innerOnSelectRecord(event.currentTarget, true)) {
                this._super.apply(this, arguments); // Default behaviour
            }
        },

        /**
         * Function to get the string ids (ej: sale.sale_order_25) of selected records
         * @returns {Array}
         * @private
         */
        _getSelectedStringIds: function () {
            let selectedRows = $("tbody .o_list_record_selector input:checked").closest("tr");
            return _.map(selectedRows, function (row) {
                return $(row).data("id");
            });
        },

        /**
         * Function to reload the pager
         * @param controlPanel
         * @private
         */
        _reload_pager: function (controlPanel) {
            controlPanel.nodes.$pager.find("button.o_enhanced_crud_pager_reload").click();
        },

        /**
         * Function to unselect rows "manually"
         */
        _unSelectRows: function () {
            this.$(".o_list_record_selector input:checked").prop("checked", false);
        },
    });

    /**
     * Enhanced CRUD List View
     */
    let EnhancedCrudListView = ListView.extend({
        config: _.extend({}, ListView.prototype.config, {
            Controller: EnhancedCrudListController,
            Renderer: EnhancedCrudListRenderer,
        }),
    });

    /**
     * Enhanced CRUD List js_class
     */
    viewRegistry.add("enhanced_crud_tree", EnhancedCrudListView);

    /**
     * Enhanced CRUD Kanban Controller
     */
    let EnhancedCrudKanbanController = KanbanController.extend(
        _.extend(EnhancedCrudCommonController, {
            buttons_template: "EnhancedCrudKanban.buttons",

            /**
             * Redefining the renderButtons method to take into account the new buttons
             * @param $node
             */
            renderButtons: function ($node) {
                let self = this;
                if (self.hasButtons) {
                    self.$buttons = $(qweb.render(self.buttons_template, {widget: this}));

                    self.$buttons.on("click", ".o_button_enhanced_crud_add", function (event) {
                        if (self._window_disposition === "new") {
                            self._enhanced_crud_generic_actionwindow();
                        } else if (self._window_disposition === "current") {
                            self._onCreateRecord(event);
                        }
                    });

                    self.$buttons.appendTo($node);
                }
            },

            /**
             * Same function as web.ListController -> _archive
             * @param ids
             * @param archive
             * @returns {*}
             * @private
             */
            _archive: function (ids, archive) {
                if (ids.length === 0) {
                    return $.when();
                }
                return this.model
                    .toggleActive(ids, !archive, this.handle)
                    .then(this.update.bind(this, {}, {reload: false}));
            },

            /**
             * Same function as web.ListController -> _onToggleArchiveState
             * @param archive
             * @param kanbanRecordDbID
             * @private
             */
            _onToggleArchiveState: function (archive, kanbanRecordDbID) {
                this._archive([kanbanRecordDbID], archive);
            },
        })
    );

    /**
     * Enhanced CRUD Kanban Renderer
     */
    let EnhancedCrudKanbanRenderer = KanbanRenderer.extend({
        init: function (parent, state, params) {
            let self = this;
            self._super.apply(self, arguments);

            self._rpc({
                model: self.state.model,
                method: "enhanced_crud_contextmenu",
            }).then(function (response) {
                if (response === "True") {
                    $.contextMenu({
                        selector: "div.oe_kanban_global_click.o_kanban_record",
                        build: function ($trigger, e) {
                            let kanbanControllerWidget = parent.getCurrentController().widget,
                                kanbanState = kanbanControllerWidget.model.get(kanbanControllerWidget.handle, {
                                    raw: true,
                                }),
                                items = {},
                                d_callbacks = {},
                                atleastone = false,
                                submenus = {};

                            for (let i in params.activeActions) {
                                if (params.activeActions[i]) {
                                    atleastone = true;
                                    if (i === "delete") {
                                        items["delete"] = {name: _lt("ECrudDelete"), icon: "delete"};
                                    } else if (i === "duplicate") {
                                        items["duplicate"] = {name: _lt("Duplicate"), icon: "copy"};
                                    }
                                }
                            }

                            if ("form" in parent._views_toolbars) {
                                let relate = parent._views_toolbars["form"]["relate"];
                                if (relate.length) {
                                    items["sep" + Object.keys(items).length] = "---------";
                                }
                                for (let i in relate) {
                                    items[relate[i].name] = {name: relate[i].name};
                                    d_callbacks[relate[i].name] = (kanbanRecordID) => {
                                        kanbanControllerWidget._onSideBarItemActionClick(relate[i], kanbanRecordID);
                                    };
                                }
                            }

                            if ("kanban" in parent._views_toolbars) {
                                let action = parent._views_toolbars["kanban"]["action"],
                                    print = parent._views_toolbars["kanban"]["print"];
                                if (action.length) {
                                    for (let i in action) {
                                        submenus[action[i].name] = {name: action[i].name};
                                        d_callbacks[action[i].name] = (kanbanRecordID) => {
                                            kanbanControllerWidget._onSideBarItemActionClick(action[i], kanbanRecordID);
                                        };
                                    }
                                    items["sep" + Object.keys(items).length] = "---------";
                                    items["fold" + Object.keys(items).length] = {
                                        name: t_4ECrudActions,
                                        items: submenus,
                                    };
                                }
                                if (print.length) {
                                    submenus = {};
                                    for (let i in print) {
                                        submenus[print[i].name] = {name: print[i].name};
                                        d_callbacks[print[i].name] = (kanbanRecordID) => {
                                            kanbanControllerWidget._onSideBarItemActionClick(print[i], kanbanRecordID);
                                        };
                                    }
                                    items["sep" + Object.keys(items).length] = "---------";
                                    items["fold" + Object.keys(items).length] = {
                                        name: t_4ECrudReports,
                                        items: submenus,
                                    };
                                }
                            }

                            if (Object.keys(items).length) {
                                items["sep" + Object.keys(items).length] = "---------";
                            }
                            if (kanbanControllerWidget.archiveEnabled) {
                                submenus = {
                                    archive: {name: _t("Archive")},
                                    unarchive: {name: _t("Unarchive")},
                                };

                                d_callbacks["archive"] = (kanbanRecordDbID) => {
                                    kanbanControllerWidget._onToggleArchiveState(true, kanbanRecordDbID);
                                };
                                d_callbacks["unarchive"] = (kanbanRecordDbID) => {
                                    kanbanControllerWidget._onToggleArchiveState(false, kanbanRecordDbID);
                                };
                            }
                            items["fold" + Object.keys(items).length] = {
                                name: t_4ECrudOthers,
                                items: submenus,
                            };

                            return {
                                items: items,
                                callback: function (key, options) {
                                    let record = options.$trigger.data("record"),
                                        recordID = record.id,
                                        dbID = record.db_id;
                                    if (key === "delete") {
                                        Dialog.confirm(self, t_4SingleDelete, {
                                            confirm_callback: () => {
                                                kanbanControllerWidget
                                                    ._rpc({
                                                        model: kanbanState.model,
                                                        method: "unlink",
                                                        context: kanbanState.getContext(),
                                                        args: [recordID],
                                                    })
                                                    .then(function () {
                                                        kanbanControllerWidget._enhanced_crud_reload();
                                                    });
                                            },
                                        });
                                    } else if (key === "duplicate") {
                                        self._rpc({
                                            model: kanbanState.model,
                                            method: "copy",
                                            context: kanbanState.getContext(),
                                            args: [recordID],
                                        }).then(function () {
                                            kanbanControllerWidget._enhanced_crud_reload();
                                        });
                                    } else {
                                        ["archive", "unarchive"].indexOf(key) !== -1
                                            ? d_callbacks[key](dbID)
                                            : d_callbacks[key](recordID);
                                    }
                                },
                            };
                        },
                    });
                }
            });
        },
    });

    /**
     * Enhanced CRUD Kanban View
     */
    let EnhancedCrudKanbanView = KanbanView.extend({
        config: _.extend({}, KanbanView.prototype.config, {
            Controller: EnhancedCrudKanbanController,
            Renderer: EnhancedCrudKanbanRenderer,
        }),
    });

    /**
     * Enhanced CRUD Kanban js_class
     */
    viewRegistry.add("enhanced_crud_kanban", EnhancedCrudKanbanView);

    /**
     * Enhanced CRUD Form Controller
     */
    let EnhancedCrudFormController = FormController.extend(
        _.extend(EnhancedCrudCommonController, {
            buttons_template: "EnhancedCrudForm.buttons",

            _reload_pager: true,

            /**
             * Function to show an dialog
             * By default an alert dialog when no modifications has been made and you still wanna save the changes
             * @param message
             * @param options
             * @param fn
             * @param owner
             * @private
             */
            _show_dialog: function (message, options, fn, owner) {
                fn = fn || "alert";
                owner = owner || this;
                message = message || t_4NoChangeMsg;
                options = options || {title: t_4Warning, buttons: [{text: _lt("Accept"), close: true}]};
                Dialog[fn](owner, message, options);
            },

            /**
             * Function to check the isDirty state of a form and if the edit action is enable
             * @param view_edit_mode
             * @param inverse
             * @param message
             * @param options
             * @param fn
             * @param owner
             * @returns {boolean}
             * @private
             */
            _check_dirty: function (view_edit_mode, inverse, message, options, fn, owner) {
                let self = this,
                    dirty_state = inverse === true ? self.isDirty() : !self.isDirty();
                if (view_edit_mode && dirty_state && self.is_action_enabled("edit")) {
                    self._show_dialog(message, options, fn, owner);
                    return true;
                }
                return false;
            },

            /**
             * Function to carry the saving process (Save, Apply | Enforce, Save & Copy, Save & Next)
             * @param applying
             * @param copying
             * @param prev
             * @param next
             * @param offset
             * @param limit
             * @returns {Function}
             * @private
             */
            _enhancedCrudSave: function (applying, copying, prev, next, offset, limit) {
                let self = this;
                return function (ev) {
                    ev.stopPropagation();
                    self._disableButtons();

                    let state = self.model.get(self.handle, {raw: true}),
                        view_edit_mode = "id" in state.data && self.displayName !== t_4ECrudAdd;

                    if (self._check_dirty(view_edit_mode)) {
                        self._enableButtons();
                        return;
                    }

                    self.saveRecord()
                        .then(function () {
                            if (self._window_disposition === "new") {
                                self._reload_pager = false;

                                let saved = self.renderer.state.data,
                                    currentControllerWidget = _enhanced_crud_findCurrentControllerWidget(self);

                                return currentControllerWidget._enhanced_crud_reload().then(function () {
                                    if (applying) {
                                        currentControllerWidget._enhanced_crud_generic_actionwindow();
                                    } else if (copying) {
                                        currentControllerWidget._enhanced_crud_generic_actionwindow(saved.id);
                                    } else {
                                        offset = offset || 0;
                                        limit = limit || 80;
                                        if (prev) {
                                            currentControllerWidget._enhanced_crud_generic_actionwindow(
                                                saved.id,
                                                t_4ECrudModify,
                                                true,
                                                false,
                                                false,
                                                offset,
                                                limit
                                            );
                                        } else if (next) {
                                            currentControllerWidget._enhanced_crud_generic_actionwindow(
                                                saved.id,
                                                t_4ECrudModify,
                                                false,
                                                true,
                                                false,
                                                offset,
                                                limit
                                            );
                                        }

                                        self._enhanced_crud_action_window_close();
                                    }
                                });
                            } else {
                                self.trigger_up("history_back");
                            }
                        })
                        .always(function () {
                            self._enableButtons();
                        });
                };
            },

            /**
             * Function to carry the pagination process within the form, checking for changes and showing confirm dialogs respectively
             * @param event
             * @param new_pos
             * @param view_edit_mode
             * @param state
             * @param offset
             * @param limit
             * @param next
             * @returns {*|Promise<T|never>}
             * @private
             */
            _enhanced_crud_form_prev_next_button_click: function (
                event,
                new_pos,
                view_edit_mode,
                state,
                offset,
                limit,
                next
            ) {
                next = next || false;
                let self = this,
                    _no_option = () => {
                        self._reload_pager = false;
                        self._enhanced_crud_generic_actionwindow(state.data.id, t_4ECrudModify, !next, next);
                    };
                if (event.currentTarget.className.indexOf(" disabled") !== -1) {
                    return;
                }
                if (new_pos) {
                    if (
                        self._check_dirty(
                            view_edit_mode,
                            true,
                            next ? t_4ChangeOnNextPagination : t_4ChangeOnPrevPagination,
                            {
                                title: _lt("Confirmation"),
                                buttons: [
                                    {
                                        text: _lt("Yes"),
                                        classes: "btn-primary",
                                        click: () =>
                                            self._enhancedCrudSave(false, false, !next, next, offset, limit)(event),
                                    },
                                    {
                                        text: _lt("No"),
                                        click: _no_option,
                                    },
                                    {
                                        text: _lt("Cancel"),
                                        close: true,
                                    },
                                ],
                            }
                        )
                    ) {
                        return;
                    }
                    self._reload_pager = false;
                    return _no_option();
                }
            },

            /**
             * Replacing the _updateButtons method to take into account the new buttons
             * @private
             */
            _updateButtons: function () {
                let self = this;
                if (self.$buttons) {
                    if (self.footerToButtons) {
                        let $footer = this.$("footer");
                        if ($footer.length) {
                            self.$buttons.empty().append($footer);
                        }
                    }

                    self._enhanced_crud_window_disposition().then(function (response) {
                        let state = self.model.get(self.handle, {raw: true}),
                            view_edit_mode = "id" in state.data && self.displayName !== t_4ECrudAdd;
                        self._window_disposition = response;
                        let new_pos = self._window_disposition === "new";
                        let current_pos = self._window_disposition === "current";

                        let offset = 0,
                            limit = 80,
                            disable_prev = true,
                            disable_next = true,
                            disable_savenext = true;
                        if (view_edit_mode) {
                            let currentControllerWidget = _enhanced_crud_findCurrentControllerWidget(self),
                                currentControllerState = currentControllerWidget.model.get(
                                    currentControllerWidget.handle,
                                    {raw: true}
                                ),
                                res_idIndexOf = currentControllerState.res_ids.indexOf(state.res_id) !== -1;

                            if (res_idIndexOf) {
                                if (currentControllerState.count === 1) {
                                    disable_prev = false;
                                    disable_next = false;
                                    disable_savenext = false;
                                } else {
                                    let stateIdIndexOf = currentControllerState.res_ids.indexOf(state.data.id) + 1;
                                    if (stateIdIndexOf === 1) {
                                        disable_prev = false;
                                    } else if (stateIdIndexOf === currentControllerState.res_ids.length) {
                                        disable_next = false;
                                        disable_savenext = false;
                                    }
                                }
                            } else {
                                disable_prev = false;
                                disable_next = false;
                                disable_savenext = false;
                            }

                            let pager = currentControllerWidget.pager;
                            if (pager.state.current_min) {
                                limit = pager.state.limit;
                                offset = pager.state.current_min > 1 ? pager.state.current_min * limit : 0;
                            }
                        }

                        let _enhanced_crud_cancel = self._onDiscard;
                        if (new_pos) {
                            _enhanced_crud_cancel = () => self._enhanced_crud_action_window_close();
                        } else if (current_pos) {
                            if (view_edit_mode) {
                                _enhanced_crud_cancel = () => self.trigger_up("history_back");
                            }
                        }

                        self.$buttons.on("click", ".o_enhanced_crud_form_prev_button", function (event) {
                            self._enhanced_crud_form_prev_next_button_click(
                                event,
                                new_pos,
                                view_edit_mode,
                                state,
                                offset,
                                limit
                            );
                        });
                        self.$buttons.find(".o_enhanced_crud_form_prev_button").toggleClass("disabled", !disable_prev);
                        self.$buttons.find(".o_enhanced_crud_form_prev_button").toggleClass("o_hidden", current_pos);

                        self.$buttons.on("click", ".o_enhanced_crud_form_next_button", function (event) {
                            self._enhanced_crud_form_prev_next_button_click(
                                event,
                                new_pos,
                                view_edit_mode,
                                state,
                                offset,
                                limit,
                                true
                            );
                        });
                        self.$buttons.find(".o_enhanced_crud_form_next_button").toggleClass("disabled", !disable_next);
                        self.$buttons.find(".o_enhanced_crud_form_next_button").toggleClass("o_hidden", current_pos);

                        self.$buttons.on(
                            "click",
                            ".o_enhanced_crud_form_cancel_button",
                            _enhanced_crud_cancel.bind(self)
                        );

                        self.$buttons.on("click", ".o_enhanced_crud_form_apply_button", self._enhancedCrudSave(true));

                        self.$buttons.on("click", ".o_enhanced_crud_form_save_button", self._enhancedCrudSave(false));

                        self.$buttons.on(
                            "click",
                            ".o_enhanced_crud_form_savecopy_button",
                            self._enhancedCrudSave(false, true)
                        );

                        self.$buttons.on("click", ".o_enhanced_crud_form_savenext_button", function (event) {
                            if (event.currentTarget.className.indexOf(" disabled") !== -1) {
                                return;
                            }
                            self._enhancedCrudSave(false, false, false, true, offset, limit)(event);
                        });
                        self.$buttons
                            .find(".o_enhanced_crud_form_savenext_button")
                            .toggleClass("disabled", !disable_savenext);

                        self.$buttons
                            .find(".o_enhanced_crud_form_buttons_create")
                            .toggleClass("o_hidden", view_edit_mode);
                        self.$buttons
                            .find(".o_enhanced_crud_form_buttons_viewedit")
                            .toggleClass("o_hidden", !view_edit_mode);

                        if (current_pos) {
                            self.pager.$("button.o_enhanced_crud_pager_reload").toggleClass("o_hidden", true);
                            self.pager.$("select.o_enhanced_crud_pagination").toggleClass("o_hidden", true);
                        }
                    });
                }
            },

            /**
             * Replacing the renderButtons method to take into account the new buttons template
             * @param $node
             */
            renderButtons: function ($node) {
                let self = this;
                let $footer = self.footerToButtons ? self.$("footer") : null;
                let mustRenderFooterButtons = $footer && $footer.length;
                if (!self.defaultButtons && !mustRenderFooterButtons) {
                    return;
                }
                self.$buttons = $("<div/>");
                if (mustRenderFooterButtons) {
                    self.$buttons.append($footer);
                } else {
                    self.$buttons.append(qweb.render(self.buttons_template, {widget: self}));
                    self._updateButtons();
                }
                self.$buttons.appendTo($node);

                let currentControllerWidget = _enhanced_crud_findCurrentControllerWidget(self);

                self._rpc({
                    model: self.modelName,
                    method: "enhanced_crud_on_formdiscarded",
                }).then(function (response) {
                    /**
                     * Everything to be done on window close
                     */
                    $("div.modal").on("hidden.bs.modal", function (event) {
                        $(document.activeElement).blur();
                        if (self._reload_pager) {
                            let state = self.model.get(self.handle, {raw: true}),
                                view_edit_mode = "id" in state.data && self.displayName !== t_4ECrudAdd;

                            if (
                                response === "True" &&
                                self._check_dirty(view_edit_mode, true, t_4ChangeOnCloseWindow, {
                                    title: _lt("Confirmation"),
                                    buttons: [
                                        {
                                            text: _lt("Yes"),
                                            classes: "btn-primary",
                                            click: (click_event) => self._enhancedCrudSave(false)(click_event),
                                        },
                                        {
                                            text: _lt("No"),
                                            click: function () {
                                                self._reload_pager = false;
                                                self.do_action({type: "ir.actions.act_window_close"});
                                            },
                                        },
                                    ],
                                })
                            ) {
                                return false;
                            } else {
                                currentControllerWidget._enhanced_crud_reload();
                            }
                        } else {
                            self._reload_pager = true;
                        }

                        let am = _enhanced_crud_findActionManager(currentControllerWidget),
                            breadcrumbs = am._getBreadcrumbs();
                        am.controlPanel.update({breadcrumbs: breadcrumbs}, {clear: false});
                    });
                });
            },

            /**
             * Redefining the _confirmSave method in order to mantain the Edit Mode on a Confirm Save operation if the
             * window disposition configuration is New
             * @param id
             * @returns {*}
             * @private
             */
            _confirmSave: function (id) {
                if (id === this.handle) {
                    if (this.mode === "readonly") {
                        return this.reload();
                    } else {
                        if (!this._window_disposition || this._window_disposition !== "new") {
                            return this._setMode("readonly");
                        } else {
                            return this._setMode("edit");
                        }
                    }
                } else {
                    let record = this.model.get(this.handle),
                        containsChangedRecord = function (value) {
                            return _.isObject(value) && (value.id === id || _.find(value.data, containsChangedRecord));
                        },
                        changedFields = _.findKey(record.data, containsChangedRecord);
                    return this.renderer.confirmChange(record, record.id, [changedFields]);
                }
            },
        })
    );

    let EnhancedCrudFormModel = BasicModel.extend({
        /**
         * Redefining the isNew method in order to return true for a Save & Copy operation
         * @param id
         */
        isNew: function (id) {
            let _context = this._getContext(this.localData[id]);
            if ("enhanced_crud_copying" in _context && _context.enhanced_crud_copying) {
                delete _context.enhanced_crud_copying;
                return true;
            } else {
                return this._super.apply(this, arguments);
            }
        },
    });

    /**
     * Enhanced CRUD Form View
     */
    let EnhancedCrudFormView = FormView.extend({
        config: _.extend({}, FormView.prototype.config, {
            Controller: EnhancedCrudFormController,
            Model: EnhancedCrudFormModel,
        }),
    });

    /**
     * Enhanced CRUD Form js_class
     */
    viewRegistry.add("enhanced_crud_form", EnhancedCrudFormView);
});
