from src.chrono_client import  MSSH

MSSH_COMMS={
    "setreference":MSSH.c_setr,
    "mkday":MSSH.c_create_day,
    "mkevent":MSSH.c_create_event,
    "mktime":MSSH.c_create_time,
    "days":MSSH.c_days,
    "mk":MSSH.c_mk,
    "show":MSSH.c_show,
    "times":MSSH.c_times,
    "generatedays":MSSH.c_gen_days,
    "clear":MSSH.c_clear,
    "clearfuture":MSSH.c_clear_future,
    "getcurrent":MSSH.c_get_current,
    "today":MSSH.c_today,
    "changeeventtime":MSSH.c_change_event_time,
    "changeeventwhat":MSSH.c_change_event_what,
    "changeeventtags":MSSH.c_change_event_tags,
    "changeevent":MSSH.c_change_event,
    "deleteday":MSSH.c_delete_day,
    "deleteevent":MSSH.c_delete_event, 
    "end":MSSH.c_end,
    "plot":MSSH.c_plot_stats,
    "plotweek":MSSH.c_plot_week,
    "note":MSSH.c_note,
    "notes":MSSH.c_notes,
    "deletenote":MSSH.c_del_note,
    "deletenoteid":MSSH.c_del_note_id,
    "deletenotes":MSSH.c_del_notes,
    "stats":MSSH.c_stats,
    "addrun":MSSH.c_add_run,
    "addsitup":MSSH.c_add_situp,
    "addpushup":MSSH.c_add_pushup,
    "addplank":MSSH.c_add_plank,
    "merge":MSSH.c_merge,
    "heatmap":MSSH.c_heatmap,
    "split": MSSH.c_split_project,
    "ourasleep": MSSH.c_oura_sleep,
    "getsleep": MSSH.c_get_sleep,
    "lastnightsleep":MSSH.c_last_sleep,
    "showruns":MSSH.c_show_run,
    "runstats":MSSH.c_run_today,
    "plotrun":MSSH.c_runplot,
    "delrun": MSSH.c_del_run,
    "delsitup": MSSH.c_del_situp,
    "delpushup": MSSH.c_del_pushup,
    "delplank": MSSH.c_del_plank,
    "fillemptydays": MSSH.c_fill_empty_days,
    "exportsport": MSSH.c_export_sport,
    "exportweek": MSSH.c_exportweek,
    "exportcsv": MSSH.c_to_csv,
    "aliases": MSSH.c_aliases,
    "runsum": MSSH.c_runsum,
    "heatmapsummary": MSSH.c_heatmap_summary,
    "heatmapanimation": MSSH.c_heatmap_animation,
    "tagsummary": MSSH.c_tag_summary,
    "tagsummarymonth": MSSH.c_summary_m,
    "exportschedule": MSSH.c_export_schedule,
    "bartagstime": MSSH.c_barplot_tags_t,
    "bartags": MSSH.c_barplot_tags,
    "rcc": MSSH.c_rel_cc,
    "topdegrees": MSSH.c_top_degrees,
    "exportgraph": MSSH.c_export_graph_data,
    "exportdatabase": MSSH.c_export_db,
    "tags": MSSH.c_tags,
    "exportgraphimage": MSSH.c_export_graph_img,
    "showgraph": MSSH.c_display_graph_img,
    "renametag": MSSH.c_rename_tag,
    "deletetag": MSSH.c_delete_tag,
    "deletebytag": MSSH.c_delete_by_tag,
    "earliestlatestplot": MSSH.c_earliest_latest_plot,
    "earliestlatestplotsleep": MSSH.c_earliest_latest_sleep,
    "mkeventdelta": MSSH.c_mk_event_by_delta,
    "runpath": MSSH.c_run_path,
    "intelliref": MSSH.c_intelli_ref,
    "gblgetsplitforce": MSSH.c_gblf,
    "gbltreeview": MSSH.c_treeview,
    "fftplot": MSSH.c_fftplot,
    "updatefunction":MSSH.c_set_function,
    "getfunction":MSSH.c_get_function,
    "reviewday":MSSH.c_review_days,
    "showsleepday":MSSH.c_show_sleep_day
}