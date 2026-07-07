from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from accounts.permissions import permission_required
from subject_management.models import TeacherSubjectAllocation
from subject_management.forms import TeacherSubjectAllocationForm


@permission_required("subject_allocations.manage")
def allocations_list(request):
    query = request.GET.get("q", "").strip()
    allocations = TeacherSubjectAllocation.objects.all()

    # Search by teacher's full name, username, or subject name
    if query:
        allocations = allocations.filter(
            teacher__full_name__icontains=query
        ) | allocations.filter(
            teacher__username__icontains=query
        ) | allocations.filter(
            subject__name__icontains=query
        )

    context = {
        "allocations": allocations.select_related("teacher", "subject", "academic_year", "academic_term", "form", "stream"),
        "q": query,
    }
    return render(request, "subject_management/allocations_list.html", context)


@permission_required("subject_allocations.manage")
def allocation_new(request):
    form = TeacherSubjectAllocationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
            messages.success(request, "Subject allocated successfully.")
            return redirect("allocations_list")
        except Exception as e:
            messages.error(request, f"Error saving allocation: {e}")

    return render(request, "subject_management/allocation_form.html", {"form": form, "title": "New Subject Allocation"})


@permission_required("subject_allocations.manage")
def allocation_edit(request, allocation_id):
    allocation = get_object_or_404(TeacherSubjectAllocation, pk=allocation_id)
    form = TeacherSubjectAllocationForm(request.POST or None, instance=allocation)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
            messages.success(request, "Allocation updated successfully.")
            return redirect("allocations_list")
        except Exception as e:
            messages.error(request, f"Error saving allocation: {e}")

    return render(request, "subject_management/allocation_form.html", {"form": form, "title": "Edit Subject Allocation", "allocation": allocation})


@permission_required("subject_allocations.manage")
def allocation_delete(request, allocation_id):
    allocation = get_object_or_404(TeacherSubjectAllocation, pk=allocation_id)
    if request.method == "POST":
        allocation.delete()
        messages.success(request, "Allocation deleted successfully.")
    return redirect("allocations_list")
