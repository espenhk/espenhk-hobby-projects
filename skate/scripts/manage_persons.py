#!/usr/bin/env python3
"""Simple CLI to manage person profiles in skate/data/people."""
import argparse
import os
import sys

# Ensure imports work when running script directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.person import Person


def list_people():
    people = Person.list_people()
    if not people:
        print("No people found in skate/data/people.")
        return
    for p in people:
        print(f"- {p['name']} ({p['filename']})")


def create_person(name, slug=None):
    p = Person.create(name, slug)
    path = p.save()
    print(f"Created: {p.name} -> {path}")


def delete_person(slug):
    directory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'people'))
    path = os.path.join(directory, f"{slug}.json")
    if os.path.exists(path):
        os.remove(path)
        print(f"Deleted: {path}")
    else:
        print(f"Not found: {path}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd')

    sub.add_parser('list')
    create = sub.add_parser('create')
    create.add_argument('name')
    create.add_argument('--slug')

    delete = sub.add_parser('delete')
    delete.add_argument('slug')

    args = parser.parse_args()

    if args.cmd == 'list':
        list_people()
    elif args.cmd == 'create':
        create_person(args.name, args.slug)
    elif args.cmd == 'delete':
        delete_person(args.slug)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
