document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const btnLoadSample = document.getElementById('btnLoadSample');
    const btnCleanData = document.getElementById('btnCleanData');
    const btnGenerateReport = document.getElementById('btnGenerateReport');
    const btnDownloadCleaned = document.getElementById('btnDownloadCleaned');
    const btnDownloadReport = document.getElementById('btnDownloadReport');
    
    const fileInfo = document.getElementById('fileInfo');
    const fileName = document.getElementById('fileName');
    
    const tableHeader = document.getElementById('tableHeader');
    const tableBody = document.getElementById('tableBody');
    
    const statTotalRows = document.getElementById('statTotalRows');
    const statDuplicates = document.getElementById('statDuplicates');
    const statMissing = document.getElementById('statMissing');
    
    const chartsSection = document.getElementById('chartsSection');
    
    // Tabs and Views
    const navDashboard = document.getElementById('navDashboard');
    const navFiles = document.getElementById('navFiles');
    const navSettings = document.getElementById('navSettings');
    
    const dashboardView = document.getElementById('dashboardView');
    const filesView = document.getElementById('filesView');
    const settingsView = document.getElementById('settingsView');
    
    const navItems = [navDashboard, navFiles, navSettings];
    const views = [dashboardView, filesView, settingsView];

    // Tab Switching Logic
    function switchTab(activeNav, activeView) {
        navItems.forEach(nav => nav.classList.remove('active'));
        views.forEach(view => view.classList.add('hidden'));
        
        activeNav.classList.add('active');
        activeView.classList.remove('hidden');
    }

    navDashboard.addEventListener('click', (e) => { e.preventDefault(); switchTab(navDashboard, dashboardView); });
    navFiles.addEventListener('click', (e) => { e.preventDefault(); switchTab(navFiles, filesView); });
    navSettings.addEventListener('click', (e) => { e.preventDefault(); switchTab(navSettings, settingsView); });
    
    // Chart Instances
    let barChartInstance = null;
    let pieChartInstance = null;

    // Toast Notification
    function showToast(message, type = 'success') {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.className = `toast show ${type}`;
        
        setTimeout(() => {
            toast.className = 'toast';
        }, 3000);
    }

    // Drag and Drop Logic
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    function handleFileUpload(file) {
        if (!file.name.endsWith('.csv')) {
            showToast('Please upload a CSV file', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        fileName.textContent = file.name;
        
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'error');
            } else {
                showToast('File uploaded successfully!');
                updateDashboard(data.stats, true);
            }
        })
        .catch(error => {
            showToast('Upload failed', 'error');
            console.error('Error:', error);
        });
    }

    // Load Sample Data
    btnLoadSample.addEventListener('click', () => {
        fetch('/load-sample', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'error');
            } else {
                fileName.textContent = 'sample_data.csv';
                showToast('Sample data loaded!');
                updateDashboard(data.stats, true);
            }
        })
        .catch(error => {
            showToast('Failed to load sample data', 'error');
            console.error('Error:', error);
        });
    });

    // Clean Data
    btnCleanData.addEventListener('click', () => {
        fetch('/clean', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'error');
            } else {
                showToast('Data cleaned successfully!');
                updateDashboard(data.stats, false);
                
                // Update Cleaning Stats
                statDuplicates.textContent = data.cleaning_summary.duplicates_removed;
                statMissing.textContent = data.cleaning_summary.missing_values_fixed;
                statTotalRows.textContent = data.cleaning_summary.final_rows;
                
                // Enable further actions
                btnGenerateReport.disabled = false;
                btnDownloadCleaned.classList.remove('hidden');
            }
        })
        .catch(error => {
            showToast('Cleaning failed', 'error');
            console.error('Error:', error);
        });
    });

    // Generate Report
    btnGenerateReport.addEventListener('click', () => {
        fetch('/report')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'error');
            } else {
                showToast('Report generated!');
                btnDownloadReport.classList.remove('hidden');
                chartsSection.classList.remove('hidden');
                
                renderCharts(data.report.bar_chart, data.report.pie_chart);
            }
        })
        .catch(error => {
            showToast('Report generation failed', 'error');
            console.error('Error:', error);
        });
    });

    // Update Dashboard UI
    function updateDashboard(stats, isInitialLoad = false) {
        // Show file info
        fileInfo.classList.remove('hidden');
        
        // Update stats
        statTotalRows.textContent = stats.total_rows;
        
        if (isInitialLoad) {
            statDuplicates.textContent = '-';
            statMissing.textContent = '-';
            btnCleanData.disabled = false;
            btnGenerateReport.disabled = true;
            btnDownloadCleaned.classList.add('hidden');
            btnDownloadReport.classList.add('hidden');
            chartsSection.classList.add('hidden');
        }

        // Render Table
        renderTable(stats.columns, stats.data);
    }

    function renderTable(columns, data) {
        // Header
        tableHeader.innerHTML = '';
        columns.forEach(col => {
            const th = document.createElement('th');
            th.textContent = col;
            tableHeader.appendChild(th);
        });

        // Body
        tableBody.innerHTML = '';
        data.forEach(row => {
            const tr = document.createElement('tr');
            columns.forEach(col => {
                const td = document.createElement('td');
                // Handle nulls nicely
                let val = row[col];
                td.textContent = (val === null || val === undefined) ? 'NaN' : val;
                tr.appendChild(td);
            });
            tableBody.appendChild(tr);
        });
    }

    function renderCharts(barData, pieData) {
        // Bar Chart
        if (barData) {
            const barCtx = document.getElementById('barChart').getContext('2d');
            if (barChartInstance) barChartInstance.destroy();
            
            barChartInstance = new Chart(barCtx, {
                type: 'bar',
                data: {
                    labels: barData.labels,
                    datasets: [{
                        label: barData.label,
                        data: barData.values,
                        backgroundColor: 'rgba(79, 70, 229, 0.6)',
                        borderColor: 'rgba(79, 70, 229, 1)',
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'top' }
                    }
                }
            });
        }

        // Pie Chart
        if (pieData) {
            const pieCtx = document.getElementById('pieChart').getContext('2d');
            if (pieChartInstance) pieChartInstance.destroy();
            
            pieChartInstance = new Chart(pieCtx, {
                type: 'doughnut',
                data: {
                    labels: pieData.labels,
                    datasets: [{
                        label: pieData.label,
                        data: pieData.values,
                        backgroundColor: [
                            'rgba(79, 70, 229, 0.8)',
                            'rgba(16, 185, 129, 0.8)',
                            'rgba(245, 158, 11, 0.8)',
                            'rgba(239, 68, 68, 0.8)',
                            'rgba(139, 92, 246, 0.8)'
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'right' }
                    }
                }
            });
        }
    }
});
