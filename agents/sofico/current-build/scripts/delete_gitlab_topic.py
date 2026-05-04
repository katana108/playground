"""
One-off script: delete a topic folder from GitLab.
Usage: python scripts/delete_gitlab_topic.py <user_folder> <topic_name>
Example: python scripts/delete_gitlab_topic.py anna document-upload-guide
"""
import os
import sys
import gitlab
import yaml

def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/delete_gitlab_topic.py <user_folder> <topic_name>")
        sys.exit(1)

    user_folder = sys.argv[1]
    topic_name = sys.argv[2]

    token = os.getenv("GITLAB_ACCESS_TOKEN")
    url = os.getenv("GITLAB_URL", "https://gitlab.com")
    project_path = os.getenv("GITLAB_LEARNERS_PROJECT", "the-smithy1/agents/sofi")
    branch = os.getenv("GITLAB_LEARNERS_BRANCH", "main")

    if not token:
        print("ERROR: GITLAB_ACCESS_TOKEN not set")
        sys.exit(1)

    gl = gitlab.Gitlab(url=url, private_token=token)
    gl.auth()
    project = gl.projects.get(project_path)

    folder_path = f"learners/{user_folder}/topics/{topic_name}"

    # List all files in the folder
    try:
        items = project.repository_tree(path=folder_path, ref=branch, recursive=True)
        files = [item["path"] for item in items if item["type"] == "blob"]
    except Exception as e:
        print(f"Could not list folder '{folder_path}': {e}")
        sys.exit(1)

    if not files:
        print(f"No files found at '{folder_path}' — already deleted or wrong path.")
        sys.exit(0)

    print(f"Deleting {len(files)} file(s) from {folder_path}:")
    for f in files:
        print(f"  {f}")

    confirm = input("Proceed? (y/n): ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        sys.exit(0)

    for file_path in files:
        try:
            f = project.files.get(file_path=file_path, ref=branch)
            project.files.delete({
                "file_path": file_path,
                "branch": branch,
                "commit_message": f"Remove {topic_name} from study topics (not a study topic)",
            })
            print(f"  Deleted: {file_path}")
        except Exception as e:
            print(f"  ERROR deleting {file_path}: {e}")

    print("Done.")

if __name__ == "__main__":
    main()
