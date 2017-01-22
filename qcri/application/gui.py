"""
The GUI to QCRI.
"""

# pylint: disable=I0011, no-member, missing-docstring

import threading
import logging
from sys import version_info
import pythoncom
from qcri.application import importer
from qcri.application import qualitycenter
# pylint: disable=I0011, import-error
if version_info.major == 2:
    import Tkinter as tk
    import tkMessageBox as messagebox
    import tkFileDialog as filedialog
    import ttk
    import Queue as queue
elif version_info.major == 3:
    import tkinter as tk
    from tkinter import messagebox
    from tkinter import filedialog
    from tkinter import ttk
    import queue


LOG = logging.getLogger(__name__)


def work_in_background(tk_, func, callback=None):
    """
    Processes func in background.
    """
    window = BusyWindow()
    done_queue = queue.Queue()

    def _process():
        func()
        done_queue.put(True)

    def _process_queue():
        try:
            done_queue.get_nowait()
            window.destroy()
            if callback:
                callback()
        except queue.Empty:
            tk_.after(100, _process_queue)

    thread = threading.Thread(target=_process)
    thread.start()
    tk_.after(100, _process_queue)


def center(widget, width, height):
    """
    Center the given widget.
    """
    screen_width = widget.winfo_screenwidth()
    screen_height = widget.winfo_screenheight()

    x_offset = int(screen_width / 2 - width / 2)
    y_offset = int(screen_height / 2 - height / 2)

    widget.geometry('{}x{}+{}+{}'.format(width, height, x_offset, y_offset))


# todo: add <rightclick> <selectall>

class QcriGui(tk.Tk):
    """
    The main window.
    """

    def __init__(self, cfg):
        tk.Tk.__init__(self)
        self.cfg = cfg  # ConfigParser

        self.qcc = None  # the Quality Center connection
        self.valid_parsers = {}
        self._cached_tests = {}  # for the treeview
        self._results = {}  # test results
        self.dir_dict = {}
        self.bug_dict = {}

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.title('QC Results Importer')
        center(self, 1200, 700)

        # tkinter widgets
        self.menubar = None
        self.remote_path = None
        self.choose_parser = None
        self.choose_results_button = None
        self.qcdir_tree = None
        self.upload_button = None
        self.choose_results_entry = None
        self.runresults_tree = None
        self.runresultsview = None
        self.header_frame = None
        self.qc_connected_frm = None
        self.qc_disconnected_frm = None
        self.link_bug = None

        self.qc_domain = tk.StringVar()
        self.attach_report = tk.IntVar()
        self.qc_project = tk.StringVar()
        self.runresultsvar = tk.StringVar()
        self.qc_conn_status = tk.BooleanVar()

        # build the gui        
        self._make()

        # style = ttk.Style()
        # style.theme_settings("default", {
        #     "TCombobox": {
        #         "configure": {"padding": 25}
        #     }
        # })

    def on_closing(self):
        """
        Called when the window is closed.

        :return:
        """
        self.disconnect_qc()
        self.destroy()

    def disconnect_qc(self):
        """
        Release the QC connection
        """
        qualitycenter.disconnect(self.qcc)
        self.qc_conn_status.set(False)

    def _make(self):
        # the Main Frame
        main_frm = tk.Frame(self)

        full_pane = tk.PanedWindow(
            main_frm, orient=tk.HORIZONTAL, sashpad=4, sashrelief=tk.RAISED)
        local_pane = self._create_local_pane(full_pane)
        remote_pane = self._create_remote_pane(full_pane)

        full_pane.add(local_pane)
        full_pane.add(remote_pane)
        full_pane.paneconfigure(local_pane, sticky='nsew', minsize=400)
        full_pane.paneconfigure(remote_pane, sticky='nsew', minsize=400)
        full_pane.grid(row=1, column=0, sticky='nsew', padx=10, pady=10)

        main_frm.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        main_frm.rowconfigure(1, weight=1)
        main_frm.columnconfigure(0, weight=1)

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def _create_local_pane(self, full_pane):
        local_pane = tk.LabelFrame(full_pane, text='Test Results')

        self.choose_results_button = tk.Button(
            local_pane,
            text='Results',
            width=15,
            command=self._load_run_results)
        self.choose_results_button.grid(
            row=0, column=0, sticky='ew', padx=10, pady=5)
        self.choose_results_entry = tk.Entry(
            local_pane, state='disabled', textvariable=self.runresultsvar)
        self.choose_results_entry.grid(
            row=0, column=1, sticky='nsew', padx=10, pady=5)
        self.choose_parser = ttk.Combobox(
            local_pane, show='', state='disabled')
        self.choose_parser.bind(
            '<<ComboboxSelected>>', self._on_parser_changed)
        self.choose_parser.grid(
            row=1, column=0, columnspan=2, sticky='nsew', padx=10, pady=7)
        self.runresultsview = TestResultsView(
            local_pane, on_selected=self._on_test_result_selected)
        self.runresultsview.grid(
            row=2, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
        self.runresultsview.rowconfigure(0, weight=1)
        self.runresultsview.columnconfigure(0, weight=1)

        local_pane.rowconfigure(2, weight=1)
        local_pane.columnconfigure(1, weight=1)
        local_pane.config(padx=10)
        return local_pane

    def _on_qc_conn_status_changed(self, *_):
        if self.qc_conn_status.get():
            self.qc_connected_frm.tkraise()
            self.upload_button.config(state=tk.NORMAL)
        else:
            self.qc_disconnected_frm.tkraise()
            self.upload_button.config(state=tk.DISABLED)
            for row in self.qcdir_tree.get_children():
                self.qcdir_tree.delete(row)
        # we didn't change selection, but fire off the events
        self._on_test_result_selected(None)

    def _create_remote_pane(self, parent):
        remote_pane = tk.LabelFrame(parent, text='Quality Center')
        self.header_frame = tk.Frame(remote_pane)

        # QC Disconnected Frame
        self.qc_disconnected_frm = tk.Frame(self.header_frame)
        if self.cfg.getboolean('main', 'history'):
            hist = importer.load_history()
        else:
            hist = None
        qc_connect_button = tk.Button(
            self.qc_disconnected_frm,
            text='Connect',
            command=lambda: LoginWindow(self.login_callback, hist),
            width=15)
        qc_connect_button.grid(row=0, column=0, sticky='ew', pady=5)
        self.qc_disconnected_frm.grid(row=0, column=0, sticky='nsew')

        # QC Connected Frame
        self.qc_connected_frm = tk.Frame(self.header_frame)
        qc_disconnect_button = tk.Button(
            self.qc_connected_frm, text='Disconnect',
            command=self.disconnect_qc, width=15)
        qc_disconnect_button.grid(
            row=0, column=0, sticky='ew', padx=(0, 10), pady=5)
        domain_label = tk.Label(
            self.qc_connected_frm, text='Domain:', font=('sans-serif 10 bold'))
        domain_label.grid(row=0, column=1)
        domain_val_lbl = tk.Label(
            self.qc_connected_frm, textvariable=self.qc_domain)
        domain_val_lbl.grid(row=0, column=2, sticky='w', padx=10)
        project_label = tk.Label(
            self.qc_connected_frm, text='Project:', font=('sans-seif 10 bold'))
        project_label.grid(row=0, column=3)
        project_val_lbl = tk.Label(
            self.qc_connected_frm, textvariable=self.qc_project)
        project_val_lbl.grid(row=0, column=4, sticky='w', padx=10)
        self.qc_connected_frm.columnconfigure(4, weight=1)
        self.qc_connected_frm.grid(row=0, column=0, sticky='nsew')
        # raise the disconnected frame first
        self.qc_disconnected_frm.tkraise()

        self.qc_conn_status.trace('w', self._on_qc_conn_status_changed)

        # self.header_frame.columnconfigure(1, weight=1)
        self.header_frame.grid(row=0, column=0, sticky='nsew', padx=10)

        # Upload Controls
        upload_frm = tk.Frame(remote_pane)
        self.attach_report.set(1)
        attach_report_chkbox = tk.Checkbutton(
            upload_frm, text='Attach Report', variable=self.attach_report)
        attach_report_chkbox.grid(row=0, column=2, sticky='e')

        self.link_bug = tk.Button(
            upload_frm,
            text='Link Bugs',
            width=15,
            command=self._on_link_bugs_clicked,
            state=tk.DISABLED)
        self.link_bug.grid(row=0, column=0, sticky='w')

        self.upload_button = tk.Button(
            upload_frm,
            text='Import',
            command=self._on_upload_btn_clicked,
            state=tk.DISABLED)
        self.upload_button.grid(row=0, column=1, sticky='ew', padx=10)
        upload_frm.columnconfigure(1, weight=1)
        upload_frm.grid(row=1, column=0, sticky='nsew', padx=10, pady=5)

        # QC Directory
        qcdir_tree_frame = tk.Frame(remote_pane)
        self.qcdir_tree = ttk.Treeview(qcdir_tree_frame, selectmode='browse')
        self.qcdir_tree.heading('#0', text='Test Lab', anchor='center')
        self.qcdir_tree.bind('<Button-3>', self._on_right_click_qc_tree)
        self.qcdir_tree.bind('<<TreeviewOpen>>', self._on_branch_opened)
        self.qcdir_tree.grid(row=0, column=0, sticky='nsew')
        ysb = ttk.Scrollbar(
            qcdir_tree_frame, orient='vertical', command=self.qcdir_tree.yview)
        ysb.grid(row=0, column=1, sticky='ns')
        self.qcdir_tree.configure(yscroll=ysb.set)
        qcdir_tree_frame.columnconfigure(0, weight=1)
        qcdir_tree_frame.rowconfigure(0, weight=1)
        qcdir_tree_frame.grid(row=2, column=0, sticky='nsew', padx=10, pady=5)

        remote_pane.columnconfigure(0, weight=1)
        remote_pane.rowconfigure(2, weight=1)
        return remote_pane

    def _on_right_click_qc_tree(self, event):
        if not self.qc_conn_status.get():
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label='Refresh', command=self.refresh_qc_directories)
        menu.post(event.x_root, event.y_root)

    def _load_run_results(self):
        filename = filedialog.askopenfilename()
        if not filename:
            return
        self.runresultsvar.set(filename)

        valid_parsers = importer.get_parsers(filename, self.cfg)
        if not valid_parsers:
            messagebox.showerror(
                'Unknown Format', 'Unable to parse this file. '
                'View log for details.')
            self.choose_parser['values'] = ['']
            self.choose_parser.current(0)
            self.choose_parser.event_generate('<<ComboboxSelected>>')
            return

        self.valid_parsers = {p.__name__: p for p in valid_parsers}
        self.choose_parser['values'] = list(self.valid_parsers.keys())
        if len(valid_parsers) > 1:
            self.choose_parser.config(state='enabled')
        self.choose_parser.current(0)
        self.choose_parser.event_generate('<<ComboboxSelected>>')

    def _on_parser_changed(self, dummy_event=None):
        filepath = self.runresultsvar.get()
        if not filepath:
            self.runresultsview.clear()
            self.runresultsview.refresh()
            return
        parser_name = self.choose_parser.get()
        if not parser_name:
            self.runresultsview.clear()
            self.runresultsview.refresh()
            return
        parser = self.valid_parsers[parser_name]
        results = []
        try:
            self.results = importer.parse_results(parser, filepath, self.cfg)
        except importer.ParserError as ex:
            messagebox.showerror(
                'Parser Error', 'An error occurred while parsing. '
                'View log for details.')
            LOG.exception(ex)
            
        self.runresultsview.populate(self.results['tests'])

    def _on_test_result_selected(self, dummy_event=None):
        has_failed_test = self.runresultsview.get_selection(failed=True)
        connected_to_qc = self.qc_conn_status.get()
        if has_failed_test and connected_to_qc:
            self.link_bug.config(state=tk.NORMAL)
        else:
            self.link_bug.config(state=tk.DISABLED, fg='black')

    def refresh_qc_directories(self):
        """
        Refresh the QC directory tree in background.
        """

        def _():
            for child in self.qcdir_tree.get_children():
                self.qcdir_tree.delete(child)
            root_ = self.qcc.TestSetTreeManager.Root
            subdirs = qualitycenter.get_subdirectories(root_)
            self.dir_dict.clear()
            for node in subdirs:
                idx = self.qcdir_tree.insert('', 'end', text=node.Name)
                self.dir_dict[idx] = node.Path
                subsubdirs = qualitycenter.get_subdirectories(node)
                if subsubdirs:
                    self.qcdir_tree.insert(idx, 'end', text='Fetching...')

        work_in_background(self, _)

    def _on_branch_opened(self, dummy_event):
        selection = self.qcdir_tree.selection()
        if not selection:
            return
        selected_idx = selection[0]
        children = self.qcdir_tree.get_children(selected_idx)
        if not children:
            return
        child = self.qcdir_tree.item(children[0])
        if child['text'] == 'Fetching...':

            def refresh(parent_idx):
                fldr = self.dir_dict[parent_idx]
                node = qualitycenter.get_qc_folder(self.qcc, fldr, create=False)
                subdirs = qualitycenter.get_subdirectories(node)
                for child in self.qcdir_tree.get_children(parent_idx):
                    self.qcdir_tree.delete(child)
                for node in subdirs:
                    idx = self.qcdir_tree.insert(parent_idx, 'end', text=node.Name)
                    self.dir_dict[idx] = node.Path
                    subsubdirs = qualitycenter.get_subdirectories(node)
                    if subsubdirs:
                        self.qcdir_tree.insert(idx, 'end', text='Fetching...')

            work_in_background(self, lambda: refresh(selected_idx))

    def select_run_result(self):
        pass

    def _on_link_bugs_clicked(self):
        failed_tests = self.runresultsview.get_selection(failed=True)
        if len(failed_tests) == 0:
            messagebox.showerror('Error', 'No failed tests in selection.')
            return
        BugWindow(self.qcc, failed_tests, self.runresultsview.refresh)

    def _on_upload_btn_clicked(self):
        selected_rows = self.runresultsview.get_selection()
        if len(selected_rows) == 0:
            messagebox.showerror('Error', 'No tests selected.')
            return
        selected_qc_dir = self.qcdir_tree.selection()
        if len(selected_qc_dir) != 1:
            messagebox.showerror('Error', 'Destination not selected.')
            return
        qcdir = self.dir_dict[selected_qc_dir[0]]
        if not qcdir:
            messagebox.showerror('Error', 'path is blank')
            return
        assert qcdir.startswith('Root\\'), qcdir
        # remove "Root\"
        qcdir = qcdir[5:]

        results = self.results.copy()
        results['tests'] = [self.runresultsview.tests[row]
                            for row in selected_rows]

        result = messagebox.askyesno(
            'Confirm',
            ('Are you sure you want to upload to the following '
             'location?\n\n{}'.format(qcdir)))
        if not result:
            return

        work_in_background(
            self,
            lambda: importer.import_results(
                self.qcc,
                qcdir,
                results,
                self.attach_report.get()),
            lambda: messagebox.showinfo('Success', 'Import complete.'))

    def login_callback(self, logincfg):
        """
        called by login window
        """
        use_history = self.cfg.getboolean('main', 'history')
        if use_history:
            hist = importer.load_history()
            importer.update_history(hist, logincfg)
        # pylint
        try:
            qcc = qualitycenter.connect(**logincfg)
        except pythoncom.com_error as ex:
            messagebox.showerror('Unable to Connect',
                                 'Error Details:\n\n{}'.format(ex))
            return False
        self.qcc = qcc
        self.qc_domain.set(logincfg['domain'])
        self.qc_project.set(logincfg['project'])
        self.qc_conn_status.set(True)
        self.refresh_qc_directories()
        return True


class LoginWindow(tk.Toplevel):
    """
    The login window.
    """

    def __init__(self, callback=None, history=None):
        tk.Toplevel.__init__(self)
        self.callback = callback
        self.history = history or {}

        self.title('QC Log In')
        self.url = None
        self.username = None
        self.password = None
        self.domain = None
        self.project = None
        center(self, 300, 300)
        self._make()

    def _make_combo(self, frame, text):
        tk.Label(frame, text='{}:'.format(text)).pack(side=tk.TOP)
        cbo = ttk.Combobox(frame, width=16, show='')
        cbo.pack(side=tk.TOP, padx=10, fill=tk.BOTH)
        cbo.bind('<Return>', self.check_password)
        cbo['values'] = self.history.get(text.lower(), [])
        if cbo['values']:
            cbo.set(cbo['values'][-1])
        return cbo

    def _make(self):
        rootfrm = tk.Frame(self, padx=10, pady=10)
        rootfrm.pack(fill=tk.BOTH, expand=True)
        self.url = self._make_combo(rootfrm, 'URL')
        self.username = self._make_combo(rootfrm, 'Username')
        tk.Label(rootfrm, text='Password:').pack(side=tk.TOP)
        self.password = tk.Entry(rootfrm, width=16, show='*')
        self.password.pack(side=tk.TOP, padx=10, fill=tk.BOTH)
        self.domain = self._make_combo(rootfrm, 'Domain')
        self.project = self._make_combo(rootfrm, 'Project')
        loginbtn = tk.Button(
            rootfrm, text="Login", width=10, pady=8,
            command=self.check_password)
        loginbtn.pack(side=tk.BOTTOM)
        self.password.bind('<Return>', self.check_password)
        loginbtn.bind('<Return>', self.check_password)

        focus = self.password
        if not self.project.get():
            focus = self.project
        if not self.domain.get():
            focus = self.domain
        if not self.username.get():
            focus = self.username
        if not self.url.get():
            focus = self.url
        focus.focus()
        self.grab_set()

    def check_password(self, dummy_event=None):
        """
        Verify their QC password.
        """
        logincfg = {
            'url': self.url.get(),
            'domain': self.domain.get(),
            'project': self.project.get(),
            'username': self.username.get(),
            'password': self.password.get()
        }
        if not any(logincfg.items()):
            return
        if self.callback(logincfg):
            self.destroy()
            self.grab_release()


class BugWindow(tk.Toplevel):

    def __init__(self, qcc, test_results, callback):
        tk.Toplevel.__init__(self)
        center(self, 900, 600)
        self.qcc = qcc
        self.callback = callback

        self._test_cache = {}
        self._bug_cache = {}
        self._make()
        self.populate_tests(test_results)
        self.refresh_qc_bugs()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.grab_set()

    def on_closing(self):
        self.destroy()
        self.grab_release()

    def _make(self):
        main_frm = tk.PanedWindow(
            self,
            borderwidth=1,
            orient=tk.HORIZONTAL,
            sashpad=4,
            sashrelief=tk.RAISED)

        left_frm = tk.Frame(main_frm)
        test_tree_frm = tk.Frame(left_frm)
        self.test_tree = ttk.Treeview(
            test_tree_frm, selectmode='browse')
        self.test_tree['show'] = 'headings'
        self.test_tree['columns'] = ('subject', 'tests', 'step', 'bug')
        self.test_tree.heading('subject', text='Subject')
        self.test_tree.heading('tests', text='Test')
        self.test_tree.heading('step', text='Failed Step')
        self.test_tree.heading('bug', text='Bug')
        self.test_tree.column('subject', width=60)
        self.test_tree.column('tests', width=150)
        self.test_tree.column('step', width=40)
        self.test_tree.column('bug', width=10)
        ysb = ttk.Scrollbar(
            test_tree_frm, orient='vertical', command=self.test_tree.yview)
        self.test_tree.grid(row=0, column=0, sticky='nsew')
        ysb.grid(row=0, column=1, sticky='ns')
        self.test_tree.configure(yscroll=ysb.set)
        test_tree_frm.columnconfigure(0, weight=1)
        test_tree_frm.rowconfigure(0, weight=1)
        test_tree_frm.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        left_frm.rowconfigure(0, weight=1)
        left_frm.columnconfigure(0, weight=1)
        main_frm.add(left_frm)

        right_frm = tk.Frame(main_frm)
        bug_tree_frame = tk.Frame(right_frm)
        self.bug_tree = ttk.Treeview(bug_tree_frame, selectmode='browse')
        self.bug_tree['show'] = 'headings'
        self.bug_tree['columns'] = (
            'bug', 'summary', 'status', 'detected_on')
        self.bug_tree.heading('bug', text='Bug', anchor='center')
        self.bug_tree.heading('summary', text='Summary', anchor='center')
        self.bug_tree.heading('status', text='Status', anchor='center')
        self.bug_tree.heading(
            'detected_on', text='Detection Date', anchor='center')
        self.bug_tree.column('bug', width=10)
        self.bug_tree.column('summary', width=50)
        self.bug_tree.column('status', width=10)
        self.bug_tree.column('detected_on', width=20)
        self.bug_tree.grid(row=0, column=0, sticky='nsew')
        ysb = ttk.Scrollbar(
            bug_tree_frame, orient='vertical', command=self.bug_tree.yview)
        ysb.grid(row=0, column=1, sticky='ns')
        self.bug_tree.configure(yscroll=ysb.set)
        bug_tree_frame.columnconfigure(0, weight=1)
        bug_tree_frame.rowconfigure(0, weight=1)
        bug_tree_frame.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        right_frm.columnconfigure(0, weight=1)
        right_frm.rowconfigure(0, weight=1)
        main_frm.add(right_frm)

        main_frm.paneconfigure(left_frm, minsize=400)
        main_frm.paneconfigure(right_frm, minsize=400)
        main_frm.grid(row=0, column=0, sticky='nsew')

        self.link_bug_button = tk.Button(
            self, text='Link Bug', command=self.link_bug)
        self.link_bug_button.grid(
            row=1, column=0, sticky='ew', padx=10, pady=10)

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def populate_tests(self, tests):
        self._test_cache.clear()
        for test in tests:
            failed_step = None
            for step in test['steps']:
                if step['status'] == 'Failed':
                    failed_step = step
                    break

            if not failed_step:
                LOG.error('failed step not found: %s', test)
                return
            idx = self.test_tree.insert('', 'end', values=(
                test['subject'],
                test['name'],
                failed_step['name'],
                test.get('bug', '-')))
            self._test_cache[idx] = test

    def refresh_qc_bugs(self):
        for child in self.bug_tree.get_children():
            self.bug_tree.delete(child)

        bugs = qualitycenter.get_bugs(self.qcc)
        self._bug_cache.clear()
        for bug in bugs:
            idx = self.bug_tree.insert('', 'end', values=(
                bug['id'],
                bug['summary'],
                bug['status'],
                bug['detection_date']))
            self._bug_cache[idx] = bug['id']

    def link_bug(self):
        sel = self.bug_tree.selection()
        if len(sel) != 1:
            return
        bug_rowidx = sel[0]
        bug = self._bug_cache[bug_rowidx]
        sel = self.test_tree.selection()
        if len(sel) != 1:
            return
        test_row = self.test_tree.item(sel[0])
        row_values = test_row['values']
        self.test_tree.item(sel[0], values=(
            row_values[0], row_values[1], row_values[2], bug))
        failed_test = self._test_cache[sel[0]]
        failed_test['bug'] = bug
        self.callback()


class BusyWindow(tk.Toplevel):
    """
    Shown when reading or writing to Quality Center.
    """

    def __init__(self):
        tk.Toplevel.__init__(self)
        center(self, 100, 50)
        frm = tk.Frame(self, padx=10, pady=10)
        spinner = tk.Label(frm, text='Busy')
        spinner.pack(fill=tk.BOTH, expand=True)
        frm.pack(fill=tk.BOTH, expand=True)

        self.config(borderwidth=2, relief=tk.RIDGE)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.grab_set()
        self.overrideredirect(1)

    def on_closing(self):
        self.destroy()
        self.grab_release()


class TestResultsView(tk.Frame):
    """
    A frame containing a summary of the parsed test results.
    """

    def __init__(self, master, on_selected=None, **kwargs):
        tk.Frame.__init__(self, master, **kwargs)
        self._cache = {}
        self.tree = ttk.Treeview(self)
        self.tree['show'] = 'headings'
        self.tree['columns'] = ('subject', 'tests', 'status', 'bug')
        self.tree.heading('subject', text='Subject')
        self.tree.heading('tests', text='Test')
        self.tree.heading('status', text='Status')
        self.tree.heading('bug', text='Bug')
        self.tree.column('subject', width=60)
        self.tree.column('tests', width=150)
        self.tree.column('status', width=40)
        self.tree.column('bug', width=10)
        self.tree.bind('<<TreeviewSelect>>', on_selected)
        ysb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        self.tree.grid(row=0, column=0, sticky='nsew')
        ysb.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscroll=ysb.set)

    @property
    def tests(self):
        return self._cache

    def clear(self):
        self._cache.clear()

    def get_selection(self, failed=False):
        selection = self.tree.selection()
        if not failed:
            return selection
        failed_tests = []
        for idx in selection:
            row = self.tree.item(idx)
            status = row['values'][2]
            if status == 'Failed':
                failed_tests.append(self._cache[idx])
        return failed_tests

    def refresh(self):
        tests = [test for test in self._cache.values()]
        self.populate(tests)

    def populate(self, tests):
        # clear the tree
        for idx in self.tree.get_children():
            self.tree.delete(idx)
        self._cache.clear()
        for test in tests:
            bug = test.get('bug', '')
            if not bug:
                bug = '-' if test['status'] == 'Failed' else ''
            idx = self.tree.insert('', 'end', values=(
                test['subject'],
                test['name'],
                test['status'],
                bug))
            self._cache[idx] = test
