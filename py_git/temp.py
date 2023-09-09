import subprocess

def run_diff_with_diffstat(file1, file2):
    try:
        # Run the 'diff' command and pipe its output to 'diffstat'
        process_diff = subprocess.Popen(["diff", file1, file2], stdout=subprocess.PIPE, text=True)
        process_diffstat = subprocess.Popen(["diffstat"], stdin=process_diff.stdout, stdout=subprocess.PIPE, text=True)
        
        # Allow process_diff to receive a SIGPIPE if process_diffstat exits
        process_diff.stdout.close()
        
        # Capture the output of 'diffstat'
        output = process_diffstat.communicate()[0]
        
        return output.rstrip('\n')
    except subprocess.CalledProcessError as e:
        return e.stdout

# Example usage:
# Note: Replace "file1.txt" and "file2.txt" with the paths to the actual files you want to compare.
file1 = "a.txt"
file2 = "b.txt"
diffstat_output = run_diff_with_diffstat(file1, file2)
print(diffstat_output)